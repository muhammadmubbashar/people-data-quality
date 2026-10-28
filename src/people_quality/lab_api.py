"""Practice workspaces attached to the existing API and role boundary."""

import hashlib
import json
import uuid
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from people_quality.demo import sample_snapshots
from people_quality.exports import workbook_inputs
from people_quality.lab_content import COACHING, GUIDES
from people_quality.lab_models import (
    Article,
    BatchCreate,
    CaseUpdate,
    Coaching,
    DefectCreate,
    DefectResolution,
    Reason,
    Requirement,
    RequirementDecision,
    TestRequest,
)
from people_quality.operations import (
    WorkflowError,
    apply_batch,
    create_run,
    documents,
    event,
    preview_batch,
    put_document,
    report_summary,
    run_context,
)
from people_quality.regression import suite
from people_quality.store import encoded


def register_lab(app, store, actor):
    router = APIRouter(prefix="/lab", tags=["Analyst practice lab"])
    Actor = Annotated[str, Depends(actor)]

    @app.exception_handler(WorkflowError)
    async def workflow_error(_, exc):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    def require(role, expected):
        if role != expected:
            raise HTTPException(403, f"This action requires the {expected} demo identity")

    with store.transaction() as db:
        for object_id, title, audience, body in GUIDES:
            if (
                db.execute(
                    "SELECT 1 FROM documents WHERE kind='article' AND id=?", (object_id,)
                ).fetchone()
                is None
            ):
                put_document(
                    db,
                    "article",
                    object_id,
                    {
                        "title": title,
                        "audience": audience,
                        "body": body,
                        "review_date": "2026-10-29",
                    },
                    "seed",
                )

    @router.get("/context/{run_id}")
    def context(run_id: str, role: Actor):
        with store.transaction() as db:
            _, value = run_context(db, run_id)
            return {k: v for k, v in value.items() if k != "captured_snapshot"}

    @router.get("/cases/{finding_id}")
    def case(finding_id: str, role: Actor):
        with store.transaction() as db:
            finding = db.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()
            if finding is None:
                raise WorkflowError("Finding not found", 404)
            row = db.execute("SELECT * FROM case_work WHERE finding_id=?", (finding_id,)).fetchone()
            value = (
                json.loads(row["payload"])
                if row
                else {
                    "owner": "GPS",
                    "priority": "medium",
                    "state": "new",
                    "root_cause": "Unknown",
                    "evidence": "",
                    "next_action": "Investigate source records",
                    "due_date": "2026-10-30",
                }
            )
            if finding["status"] != "open":
                value["state"] = finding["status"]
            return {"finding_id": finding_id, "version": row["version"] if row else 0, **value}

    @router.put("/cases/{finding_id}")
    def update_case(finding_id: str, request: CaseUpdate, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            finding = db.execute("SELECT status FROM findings WHERE id=?", (finding_id,)).fetchone()
            if finding is None:
                raise WorkflowError("Finding not found", 404)
            if finding["status"] != "open":
                raise WorkflowError("Closed findings cannot be edited", 409)
            row = db.execute(
                "SELECT version FROM case_work WHERE finding_id=?", (finding_id,)
            ).fetchone()
            version = row[0] if row else 0
            if request.expected_version != version:
                raise WorkflowError("Case changed; refresh before saving", 409)
            if request.state == "closed_no_change":
                pending = db.execute(
                    "SELECT 1 FROM changes WHERE finding_id=? AND status IN ('pending','approved')",
                    (finding_id,),
                ).fetchone()
                batch_pending = any(
                    any(i["finding_id"] == finding_id for i in json.loads(b["payload"])["items"])
                    for b in db.execute(
                        "SELECT payload FROM batches WHERE status IN ('pending','approved')"
                    )
                )
                if pending or batch_pending:
                    raise WorkflowError(
                        "Cancel outstanding corrections before closing this case", 409
                    )
            body = request.model_dump(mode="json", exclude={"expected_version"})
            db.execute(
                "INSERT OR REPLACE INTO case_work VALUES(?,?,?)",
                (finding_id, encoded(body), version + 1),
            )
            if request.state == "closed_no_change":
                db.execute(
                    "UPDATE findings SET status='closed_no_change' WHERE id=?", (finding_id,)
                )
            event(db, finding_id, role, "case_updated", encoded(body))
        return {"finding_id": finding_id, "version": version + 1, **body}

    @router.get("/events/{object_id}")
    def history(object_id: str, role: Actor):
        with store.transaction() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT actor,action,detail,created_at FROM lab_events "
                    "WHERE object_id=? ORDER BY id",
                    (object_id,),
                )
            ]

    @router.post("/changes/{change_id}/{action}")
    def decide_single(change_id: str, action: str, request: Reason, role: Actor):
        if action not in ("reject", "cancel"):
            raise WorkflowError("Unknown action", 404)
        require(role, "reviewer" if action == "reject" else "analyst")
        with store.transaction() as db:
            row = db.execute("SELECT * FROM changes WHERE id=?", (change_id,)).fetchone()
            if row is None:
                raise WorkflowError("Change not found", 404)
            allowed_states = ("pending",) if action == "reject" else ("pending", "approved")
            if row["status"] not in allowed_states:
                raise WorkflowError("Request cannot be changed in this state", 409)
            status = "rejected" if action == "reject" else "cancelled"
            db.execute("UPDATE changes SET status=? WHERE id=?", (status, change_id))
            db.execute(
                "INSERT INTO events(change_id,actor,action) VALUES(?,?,?)",
                (change_id, role, status),
            )
            event(db, change_id, role, status, request.reason)
        return {"id": change_id, "status": status}

    @router.post("/batches/preview")
    def preview(request: BatchCreate, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            return preview_batch(db, request.items)

    @router.post("/batches")
    def submit_batch(request: BatchCreate, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            proposal = preview_batch(db, request.items)
            proposal["reason"] = request.reason
            batch_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO batches(id,run_id,payload,status,requested_by) VALUES(?,?,?,?,?)",
                (batch_id, proposal["run_id"], encoded(proposal), "pending", role),
            )
            event(db, batch_id, role, "batch_requested", encoded(proposal))
        return {"id": batch_id, "status": "pending", **proposal}

    @router.get("/batches")
    def batches(role: Actor):
        with store.transaction() as db:
            return [
                {**dict(r), "proposal": json.loads(r["payload"])}
                for r in db.execute("SELECT * FROM batches ORDER BY rowid DESC")
            ]

    @router.post("/batches/{batch_id}/{action}")
    def decide_batch(batch_id: str, action: str, request: Reason, role: Actor):
        if action == "apply":
            require(role, "operator")
            return apply_batch(store, batch_id, role)
        if action not in ("approve", "reject", "cancel"):
            raise WorkflowError("Unknown action", 404)
        require(role, "analyst" if action == "cancel" else "reviewer")
        with store.transaction() as db:
            row = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
            if row is None:
                raise WorkflowError("Batch not found", 404)
            allowed_states = ("pending", "approved") if action == "cancel" else ("pending",)
            if row["status"] not in allowed_states:
                raise WorkflowError("Batch cannot be reviewed or cancelled in this state", 409)
            if action == "approve" and row["requested_by"] == role:
                raise WorkflowError("Requester cannot approve their own batch", 403)
            status = {"approve": "approved", "reject": "rejected", "cancel": "cancelled"}[action]
            reviewer = row["reviewed_by"] if action == "cancel" else role
            db.execute(
                "UPDATE batches SET status=?,reviewed_by=? WHERE id=?", (status, reviewer, batch_id)
            )
            event(db, batch_id, role, f"batch_{status}", request.reason)
        return {"id": batch_id, "status": status}

    @router.get("/reports/{run_id}")
    def reports(
        run_id: str,
        role: Actor,
        source: str | None = None,
        status: str | None = None,
        rule: str | None = None,
    ):
        with store.transaction() as db:
            return report_summary(db, run_id, source, status, rule)

    @router.get("/trends")
    def trends(role: Actor):
        groups = {}
        with store.transaction() as db:
            for row in db.execute("SELECT id,as_of FROM runs ORDER BY rowid"):
                run, context = run_context(db, row["id"])
                ids = sorted(
                    {r["worker_id"].strip() for r in context["captured_snapshot"]["workday"]}
                )
                fingerprint = hashlib.sha256(encoded(ids).encode()).hexdigest()[:12]
                key = f"{context['cohort']} / {context['policy']} / {fingerprint}"
                value = {
                    "run_id": run["id"],
                    "as_of": run["as_of"],
                    "workers": len(ids),
                    "initial_findings": len(context["initial_findings"]),
                    "comparable": all(d == run["as_of"] for d in context["source_dates"].values()),
                }
                groups.setdefault(key, {})[run["as_of"]] = value
        return {
            "groups": [
                {"cohort": key, "points": sorted(points.values(), key=lambda p: p["as_of"])}
                for key, points in groups.items()
            ],
            "basis": "Latest capture per day; initial audit counts, not later case closures. "
            "Matching IDs and policy do not prove identical business populations.",
        }

    @router.get("/exports/{run_id}.zip")
    def export_inputs(run_id: str, role: Actor, view: Literal["captured", "current"] = "captured"):
        with store.transaction() as db:
            run, context = run_context(db, run_id)
            snapshots = (
                context["captured_snapshot"] if view == "captured" else json.loads(run["snapshots"])
            )
            data = workbook_inputs(snapshots, context, view)
        return Response(
            data,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="synthetic-excel-practice.zip"'},
        )

    @router.post("/practice-history")
    def practice_history(role: Actor):
        require(role, "analyst")
        results = []
        for index in range(3):
            snapshots = sample_snapshots()
            if index >= 1:
                snapshots["payroll"][34]["cost_centre"] = "C100"
            if index >= 2:
                snapshots["core"][44]["cost_centre"] = "C100"
            results.append(
                create_run(
                    store,
                    snapshots,
                    date(2026, 10, 27) + timedelta(days=index),
                    cohort="history-practice",
                )
            )
        return {"runs": results, "explanation": "Three independently generated synthetic captures"}

    @router.post("/timing-scenario")
    def timing_scenario(role: Actor):
        require(role, "analyst")
        return create_run(
            store,
            sample_snapshots(),
            date(2026, 10, 29),
            {"workday": "2026-10-29", "payroll": "2026-10-28", "core": "2026-10-29"},
            cohort="timing-practice",
        )

    @router.get("/articles")
    def articles(role: Actor, q: Annotated[str, Query(max_length=100)] = ""):
        with store.transaction() as db:
            return [
                a
                for a in documents(db, "article")
                if q.lower() in (a["title"] + " " + a["body"]).lower()
            ]

    @router.put("/articles/{article_id}")
    def save_article(article_id: str, request: Article, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            return put_document(
                db,
                "article",
                article_id,
                request.model_dump(mode="json", exclude={"expected_version"}),
                role,
                request.expected_version,
            )

    @router.get("/documents/{kind}/{object_id}/versions")
    def versions(kind: str, object_id: str, role: Actor):
        with store.transaction() as db:
            return [
                {
                    "version": r["version"],
                    "actor": r["actor"],
                    "created_at": r["created_at"],
                    **json.loads(r["payload"]),
                }
                for r in db.execute(
                    "SELECT * FROM documents WHERE kind=? AND id=? ORDER BY version",
                    (kind, object_id),
                )
            ]

    @router.get("/coaching")
    def coaching(role: Actor):
        with store.transaction() as db:
            return {"prompts": COACHING, "sessions": documents(db, "coaching")}

    @router.post("/coaching")
    def save_coaching(request: Coaching, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            return put_document(db, "coaching", str(uuid.uuid4()), request.model_dump(), role)

    @router.get("/requirements")
    def requirements(role: Actor):
        with store.transaction() as db:
            return documents(db, "requirement")

    @router.put("/requirements/{requirement_id}")
    def save_requirement(requirement_id: str, request: Requirement, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            body = request.model_dump(exclude={"expected_version"})
            body["status"] = "proposed"
            return put_document(
                db, "requirement", requirement_id, body, role, request.expected_version
            )

    @router.post("/requirements/{requirement_id}/accept")
    def accept_requirement(requirement_id: str, request: RequirementDecision, role: Actor):
        require(role, "reviewer")
        with store.transaction() as db:
            record = next(
                (r for r in documents(db, "requirement") if r["id"] == requirement_id), None
            )
            if not record:
                raise WorkflowError("Requirement not found", 404)
            if record["status"] != "proposed":
                raise WorkflowError("Only proposed requirements may be accepted", 409)
            body = {k: v for k, v in record.items() if k not in ("id", "version", "created_at")}
            body.update(status="accepted", review_reason=request.reason)
            return put_document(
                db, "requirement", requirement_id, body, role, request.expected_version
            )

    @router.post("/test-runs")
    def test_run(request: TestRequest, role: Actor):
        require(role, "analyst")
        result, object_id = suite(request.release), str(uuid.uuid4())
        with store.transaction() as db:
            db.execute(
                "INSERT INTO test_runs(id,release,payload,actor) VALUES(?,?,?,?)",
                (object_id, request.release, encoded(result), role),
            )
        return {"id": object_id, **result}

    @router.get("/test-runs")
    def test_runs(role: Actor):
        with store.transaction() as db:
            return [
                {"id": r["id"], "created_at": r["created_at"], **json.loads(r["payload"])}
                for r in db.execute("SELECT * FROM test_runs ORDER BY rowid DESC")
            ]

    def get_test(db, object_id):
        row = db.execute("SELECT payload FROM test_runs WHERE id=?", (object_id,)).fetchone()
        if row is None:
            raise WorkflowError("Test run not found", 404)
        return json.loads(row["payload"])

    @router.get("/defects")
    def defects(role: Actor):
        with store.transaction() as db:
            return documents(db, "defect")

    @router.post("/defects")
    def create_defect(request: DefectCreate, role: Actor):
        require(role, "analyst")
        with store.transaction() as db:
            result = get_test(db, request.test_run_id)
            failed = next((r for r in result["results"] if r["name"] == request.case_name), None)
            if failed is None or failed["passed"]:
                raise WorkflowError("A defect must reference a failed acceptance test")
            body = {
                **request.model_dump(),
                "status": "open",
                "release": result["release"],
                "expected": failed["expected"],
                "actual": failed["actual"],
            }
            return put_document(db, "defect", str(uuid.uuid4()), body, role)

    @router.post("/defects/{defect_id}/resolve")
    def resolve_defect(defect_id: str, request: DefectResolution, role: Actor):
        require(role, "reviewer")
        with store.transaction() as db:
            defect = next((r for r in documents(db, "defect") if r["id"] == defect_id), None)
            if not defect:
                raise WorkflowError("Defect not found", 404)
            if defect["status"] != "open":
                raise WorkflowError("Defect is already resolved", 409)
            test = get_test(db, request.passing_test_run_id)
            matching = next((r for r in test["results"] if r["name"] == defect["case_name"]), None)
            if not matching or not matching["passed"] or not test["passed"]:
                raise WorkflowError(
                    "A passing retest of the case and complete suite is required", 409
                )
            body = {k: v for k, v in defect.items() if k not in ("id", "version", "created_at")}
            body.update(
                status="resolved",
                passing_test_run_id=request.passing_test_run_id,
                resolution=request.reason,
            )
            return put_document(db, "defect", defect_id, body, role, request.expected_version)

    app.include_router(router)
