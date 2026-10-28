"""Transactional practice services. Vendor connections are deliberately absent."""

import json
import math
import uuid
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import date

from people_quality.domain import COST_CENTRES, SOURCES, audit
from people_quality.store import encoded


class WorkflowError(Exception):
    def __init__(self, message: str, status: int = 422):
        self.message = message
        self.status = status
        super().__init__(message)


def event(db, object_id, actor, action, detail=""):
    db.execute(
        "INSERT INTO lab_events(object_id,actor,action,detail) VALUES(?,?,?,?)",
        (object_id, actor, action, detail),
    )


def run_context(db, run_id):
    run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if run is None:
        raise WorkflowError("Audit run not found", 404)
    stored = db.execute("SELECT payload FROM run_context WHERE run_id=?", (run_id,)).fetchone()
    if stored:
        return run, json.loads(stored["payload"])
    # Old runs remain usable without pretending a migrated snapshot is an original capture.
    findings = [
        json.loads(r["payload"])
        for r in db.execute("SELECT payload FROM findings WHERE run_id=?", (run_id,))
    ]
    context = {
        "source_dates": dict.fromkeys(SOURCES, run["as_of"]),
        "initial_findings": findings,
        "captured_snapshot": json.loads(run["snapshots"]),
        "capture_kind": "migration_current_state",
        "cohort": "legacy",
        "policy": "v1",
    }
    db.execute("INSERT INTO run_context VALUES(?,?)", (run_id, encoded(context)))
    return run, context


def create_run(store, snapshots, as_of, source_dates=None, cohort="practice"):
    dates = dict.fromkeys(SOURCES, as_of.isoformat()) if source_dates is None else source_dates
    if set(dates) != set(SOURCES):
        raise WorkflowError("Supply exactly one date for workday, payroll and core")
    for value in dates.values():
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise WorkflowError("Source dates must be ISO dates") from exc
    findings = audit(snapshots, as_of, dates)
    run_id = str(uuid.uuid4())
    context = {
        "source_dates": dates,
        "initial_findings": [asdict(f) for f in findings],
        "captured_snapshot": deepcopy(snapshots),
        "capture_kind": "original_import",
        "cohort": cohort,
        "policy": "v2",
    }
    with store.transaction() as db:
        db.execute(
            "INSERT INTO runs(id,as_of,snapshots) VALUES(?,?,?)",
            (run_id, as_of.isoformat(), encoded(snapshots)),
        )
        for item in findings:
            db.execute(
                "INSERT INTO findings(id,run_id,payload) VALUES(?,?,?)",
                (str(uuid.uuid4()), run_id, encoded(asdict(item))),
            )
        db.execute("INSERT INTO run_context VALUES(?,?)", (run_id, encoded(context)))
    return {"run_id": run_id, "findings": len(findings), "synthetic_demo": True}


def converted_value(field, text, snapshots, worker_id):
    if field == "cost_centre":
        if text not in COST_CENTRES:
            raise WorkflowError("Unknown cost centre")
        return text
    if field == "fte":
        try:
            value = float(text)
        except ValueError as exc:
            raise WorkflowError("FTE must be numeric") from exc
        if not math.isfinite(value) or not 0 < value <= 1:
            raise WorkflowError("FTE must be finite, greater than zero and at most one")
        return value
    if field == "manager_id":
        candidates = [r for r in snapshots["workday"] if r["worker_id"].strip() == text]
        if text == worker_id or len(candidates) != 1:
            raise WorkflowError("Manager must be another unique HR worker")
        return text
    if field == "hire_date":
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise WorkflowError("Hire date must be an ISO date") from exc
        return text
    raise WorkflowError("This finding needs source-owner investigation, not a field replacement")


def preview_batch(db, items):
    run_id, snapshots, context, run = None, None, None, None
    seen, prepared = set(), []
    for item in items:
        row = db.execute("SELECT * FROM findings WHERE id=?", (item.finding_id,)).fetchone()
        if row is None:
            raise WorkflowError("Finding not found", 404)
        if row["status"] != "open":
            raise WorkflowError("Only open findings may be corrected", 409)
        if run_id is None:
            run_id = row["run_id"]
            run, context = run_context(db, run_id)
            snapshots = json.loads(run["snapshots"])
        if row["run_id"] != run_id:
            raise WorkflowError("A batch must belong to one audit run")
        if any(d != run["as_of"] for d in context["source_dates"].values()):
            raise WorkflowError("Obtain comparable source dates before requesting corrections")
        finding = json.loads(row["payload"])
        target = (finding["source"], finding["worker_id"], finding["field"])
        if target in seen:
            raise WorkflowError("Duplicate field target in batch")
        seen.add(target)
        matches = [
            r
            for r in snapshots[finding["source"]]
            if r["worker_id"].strip() == finding["worker_id"]
        ]
        if len(matches) != 1 or finding["field"] not in matches[0]:
            raise WorkflowError("Correction target is missing or ambiguous")
        old = matches[0][finding["field"]]
        if str(old) != finding["observed"]:
            raise WorkflowError("Source changed since audit; investigate again", 409)
        new = converted_value(finding["field"], item.new_value, snapshots, finding["worker_id"])
        if old == new:
            raise WorkflowError("Proposed value is unchanged")
        if finding["rule"] == "COST_CENTRE_MISMATCH" and new != finding["expected"]:
            raise WorkflowError("Proposed cost centre conflicts with the demo HR ownership policy")
        prepared.append(
            {
                "finding_id": item.finding_id,
                "source": finding["source"],
                "worker_id": finding["worker_id"],
                "field": finding["field"],
                "old_value": old,
                "new_value": new,
                "rule": finding["rule"],
            }
        )
    candidate = deepcopy(snapshots)
    apply_items(candidate, prepared)
    before = audit(snapshots, date.fromisoformat(run["as_of"]), context["source_dates"])
    after = audit(candidate, date.fromisoformat(run["as_of"]), context["source_dates"])
    validate_outcome(before, after, prepared)
    return {
        "run_id": run_id,
        "items": prepared,
        "before_count": len(before),
        "after_count": len(after),
        "valid": True,
        "applied": False,
    }


def apply_items(snapshots, items):
    for item in items:
        matches = [
            r for r in snapshots[item["source"]] if r["worker_id"].strip() == item["worker_id"]
        ]
        if len(matches) != 1 or matches[0][item["field"]] != item["old_value"]:
            raise WorkflowError("A source value changed since review; batch remains unapplied", 409)
        matches[0][item["field"]] = item["new_value"]


def validate_outcome(before, after, items):
    before_keys = {f.signature for f in before}
    after_keys = {f.signature for f in after}
    targets = {(i["rule"], i["worker_id"], i["source"], i["field"]) for i in items}
    if targets & after_keys or after_keys - before_keys:
        raise WorkflowError(
            "Revalidation failed: target remains or a new finding was introduced", 409
        )


def apply_batch(store, batch_id, actor):
    with store.transaction() as db:
        batch = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if batch is None:
            raise WorkflowError("Batch not found", 404)
        if batch["status"] == "applied":
            return {"id": batch_id, "status": "applied", "already_applied": True}
        if batch["status"] != "approved":
            raise WorkflowError("Separate reviewer approval is required", 409)
        run, context = run_context(db, batch["run_id"])
        snapshots = json.loads(run["snapshots"])
        proposal = json.loads(batch["payload"])
        before = audit(snapshots, date.fromisoformat(run["as_of"]), context["source_dates"])
        apply_items(snapshots, proposal["items"])
        after = audit(snapshots, date.fromisoformat(run["as_of"]), context["source_dates"])
        validate_outcome(before, after, proposal["items"])
        db.execute("UPDATE runs SET snapshots=? WHERE id=?", (encoded(snapshots), run["id"]))
        for item in proposal["items"]:
            db.execute("UPDATE findings SET status='resolved' WHERE id=?", (item["finding_id"],))
        db.execute("UPDATE batches SET status='applied' WHERE id=?", (batch_id,))
        event(db, batch_id, actor, "batch_applied_and_revalidated", encoded(proposal["items"]))
    return {"id": batch_id, "status": "applied", "remaining": len(after)}


def documents(db, kind):
    return [
        {
            "id": r["id"],
            "version": r["version"],
            "created_at": r["created_at"],
            **json.loads(r["payload"]),
        }
        for r in db.execute(
            """SELECT d.* FROM documents d WHERE kind=? AND version=(
        SELECT MAX(version) FROM documents WHERE kind=d.kind AND id=d.id) ORDER BY rowid DESC""",
            (kind,),
        )
    ]


def put_document(db, kind, object_id, payload, actor, expected_version=0):
    latest = (
        db.execute(
            "SELECT MAX(version) FROM documents WHERE kind=? AND id=?", (kind, object_id)
        ).fetchone()[0]
        or 0
    )
    if latest != expected_version:
        raise WorkflowError("Document changed; refresh before saving", 409)
    version = latest + 1
    db.execute(
        "INSERT INTO documents(kind,id,version,payload,actor) VALUES(?,?,?,?,?)",
        (kind, object_id, version, encoded(payload), actor),
    )
    event(db, object_id, actor, f"{kind}_version_saved", str(version))
    return {"id": object_id, "version": version, **payload}


def report_summary(db, run_id, source=None, status=None, rule=None):
    run, context = run_context(db, run_id)
    rows = [
        {"id": r["id"], "status": r["status"], **json.loads(r["payload"])}
        for r in db.execute("SELECT * FROM findings WHERE run_id=?", (run_id,))
    ]
    selected = [
        r
        for r in rows
        if (not source or r["source"] == source)
        and (not status or r["status"] == status)
        and (not rule or r["rule"] == rule)
    ]
    open_cases = [r for r in selected if r["status"] == "open"]
    workers = {r["worker_id"].strip() for r in json.loads(run["snapshots"])["workday"]}
    cases = []
    for row in selected:
        record = db.execute(
            "SELECT payload FROM case_work WHERE finding_id=?", (row["id"],)
        ).fetchone()
        cases.append(
            {
                **row,
                "root_cause": json.loads(record["payload"])["root_cause"] if record else "Unknown",
            }
        )
    return {
        "run_id": run_id,
        "as_of": run["as_of"],
        "cohort": context["cohort"],
        "source_dates": context["source_dates"],
        "policy": context["policy"],
        "distinct_hr_workers": len(workers),
        "filtered_cases": len(selected),
        "open_cases": len(open_cases),
        "affected_workers": len({r["worker_id"] for r in open_cases if r["worker_id"] != "ALL"}),
        "by_rule": dict(Counter(r["rule"] for r in open_cases)),
        "by_root_cause": dict(Counter(r["root_cause"] for r in cases if r["status"] == "open")),
        "rows": cases,
        "captured_findings": len(context["initial_findings"]),
    }
