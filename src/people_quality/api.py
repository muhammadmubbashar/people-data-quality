"""Local demo API. Identity is derived from per-role keys, never client role headers."""

import csv
import io
import json
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from people_quality.demo import sample_snapshots
from people_quality.domain import COST_CENTRES, Worker
from people_quality.lab_api import register_lab
from people_quality.operations import audit_for_context, run_context
from people_quality.operations import create_run as create_practice_run
from people_quality.store import Store, encoded
from people_quality.workday import ConnectionError as WorkdayConnectionError
from people_quality.workday import capture_summary
from people_quality.workday_mapping import import_stage, read_stage


@dataclass(frozen=True)
class Settings:
    db_path: str
    keys: dict[str, str]
    mode: str = "demo"

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            os.getenv("DB_PATH", "data/local/people-quality.db"),
            {
                role: os.getenv(f"{role.upper()}_KEY", "")
                for role in ("analyst", "reviewer", "operator")
            },
            os.getenv("APP_MODE", "demo"),
        )


class ImportRequest(BaseModel):
    as_of: date
    workday: list[Worker] = Field(min_length=1, max_length=5000)
    payroll: list[Worker] = Field(min_length=1, max_length=5000)
    core: list[Worker] = Field(min_length=1, max_length=5000)
    source_dates: dict[str, date] | None = None


class ChangeRequest(BaseModel):
    finding_id: str
    new_value: str = Field(min_length=1, max_length=30)
    reason: str = Field(min_length=10, max_length=500)


class BatchRequest(BaseModel):
    changes: list[ChangeRequest] = Field(min_length=1, max_length=100)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.mode != "demo":
        raise RuntimeError("Production mode is not implemented. See docs/production.md.")
    if set(settings.keys) != {"analyst", "reviewer", "operator"}:
        raise RuntimeError("All three demo roles must be configured")
    if len(set(settings.keys.values())) != 3 or any(len(k) < 24 for k in settings.keys.values()):
        raise RuntimeError("Run scripts/setup.ps1: distinct random demo keys are required")
    store = Store(settings.db_path)
    app = FastAPI(title="People Data Quality — independent synthetic demo", version="0.3.0")

    def actor(x_api_key: Annotated[str | None, Header()] = None) -> str:
        for role, key in settings.keys.items():
            if x_api_key and secrets.compare_digest(x_api_key, key):
                return role
        raise HTTPException(401, "A valid local demo key is required")

    Actor = Annotated[str, Depends(actor)]

    def allowed(role, expected):
        if role != expected:
            raise HTTPException(403, f"This action requires the {expected} demo identity")

    def get_run(db, run_id):
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Run not found")
        return row

    def new_run(snapshots, as_of, source_dates=None):
        return create_practice_run(store, snapshots, as_of, source_dates)

    def validate_change(db, request):
        row = db.execute("SELECT * FROM findings WHERE id=?", (request.finding_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Finding not found")
        payload = json.loads(row["payload"])
        _, context = run_context(db, row["run_id"])
        if context.get("provenance") and payload["source"] == "workday":
            raise HTTPException(422, "Imported Workday source is read-only")
        run = get_run(db, row["run_id"])
        if any(d != run["as_of"] for d in context["source_dates"].values()):
            raise HTTPException(422, "Obtain comparable source dates before corrections")
        if row["status"] != "open":
            raise HTTPException(409, "Finding is already resolved")
        if payload["field"] != "cost_centre":
            raise HTTPException(422, "Phase 1 supports cost-centre corrections only")
        if request.new_value not in context.get("audit_policy", {}).get(
            "cost_centres", COST_CENTRES
        ):
            raise HTTPException(422, "Cost centre must be in this run's verified reference set")
        if request.new_value == payload["observed"]:
            raise HTTPException(422, "Proposed value must differ from the observed value")
        if payload["rule"] == "COST_CENTRE_MISMATCH" and request.new_value != payload["expected"]:
            raise HTTPException(422, "Value conflicts with the current demo HR source of truth")
        return row, payload

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "synthetic-demo", "version": "0.3.0"}

    @app.post("/runs/demo")
    def demo_run(role: Actor):
        allowed(role, "analyst")
        return new_run(sample_snapshots(), date(2026, 10, 29))

    @app.post("/runs")
    def import_run(request: ImportRequest, role: Actor):
        allowed(role, "analyst")
        snapshots = {
            source: [worker.model_dump() for worker in getattr(request, source)]
            for source in ("workday", "payroll", "core")
        }
        dates = (
            {k: v.isoformat() for k, v in request.source_dates.items()}
            if request.source_dates is not None
            else None
        )
        return new_run(snapshots, request.as_of, dates)

    @app.get("/runs")
    def runs(role: Actor):
        with store.transaction() as db:
            return [
                dict(r)
                for r in db.execute("SELECT id,as_of,created_at FROM runs ORDER BY rowid DESC")
            ]

    @app.get("/runs/{run_id}/findings")
    def findings(run_id: str, role: Actor):
        with store.transaction() as db:
            get_run(db, run_id)
            return [
                {"id": r["id"], "status": r["status"], **json.loads(r["payload"])}
                for r in db.execute("SELECT * FROM findings WHERE run_id=?", (run_id,))
            ]

    @app.get("/runs/{run_id}/records/{worker_id}")
    def records(run_id: str, worker_id: str, role: Actor):
        with store.transaction() as db:
            run = get_run(db, run_id)
            return {
                "as_of": run["as_of"],
                "sources": {
                    source: [r for r in rows if r["worker_id"].strip() == worker_id]
                    for source, rows in json.loads(run["snapshots"]).items()
                },
            }

    @app.post("/changes/dry-run")
    def dry_run(request: BatchRequest, role: Actor):
        allowed(role, "analyst")
        errors, seen, run_ids = [], set(), set()
        with store.transaction() as db:
            for index, change in enumerate(request.changes):
                try:
                    row, payload = validate_change(db, change)
                    key = (row["run_id"], payload["source"], payload["worker_id"], payload["field"])
                    if key in seen:
                        raise HTTPException(422, "Duplicate target in batch")
                    seen.add(key)
                    run_ids.add(row["run_id"])
                except HTTPException as exc:
                    errors.append({"row": index + 1, "message": exc.detail})
        if len(run_ids) > 1:
            errors.append({"row": 0, "message": "A batch must belong to one snapshot run"})
        return {
            "valid": not errors,
            "rows": len(request.changes),
            "errors": errors,
            "applied": False,
            "note": "Preview only; no batch execution in phase 1",
        }

    @app.post("/changes")
    def request_change(request: ChangeRequest, role: Actor):
        allowed(role, "analyst")
        with store.transaction() as db:
            _, payload = validate_change(db, request)
            change_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO changes
                (id,finding_id,proposed,old_value,reason,requested_by) VALUES(?,?,?,?,?,?)""",
                (
                    change_id,
                    request.finding_id,
                    request.new_value,
                    payload["observed"],
                    request.reason,
                    role,
                ),
            )
            db.execute(
                "INSERT INTO events(change_id,actor,action) VALUES(?,?,?)",
                (change_id, role, "requested"),
            )
        return {"change_id": change_id, "status": "pending"}

    @app.get("/changes")
    def changes(role: Actor):
        with store.transaction() as db:
            return [dict(r) for r in db.execute("SELECT * FROM changes ORDER BY rowid DESC")]

    @app.post("/changes/{change_id}/approve")
    def approve(change_id: str, role: Actor):
        allowed(role, "reviewer")
        with store.transaction() as db:
            row = db.execute("SELECT * FROM changes WHERE id=?", (change_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Change not found")
            if row["requested_by"] == role or row["status"] != "pending":
                raise HTTPException(409, "Change cannot be approved in this state")
            db.execute(
                "UPDATE changes SET status='approved',reviewed_by=? WHERE id=?", (role, change_id)
            )
            db.execute(
                "INSERT INTO events(change_id,actor,action) VALUES(?,?,?)",
                (change_id, role, "approved"),
            )
        return {"change_id": change_id, "status": "approved"}

    @app.post("/changes/{change_id}/apply")
    def apply(change_id: str, role: Actor):
        allowed(role, "operator")
        with store.transaction() as db:
            change = db.execute("SELECT * FROM changes WHERE id=?", (change_id,)).fetchone()
            if change is None:
                raise HTTPException(404, "Change not found")
            if change["status"] == "applied":
                return {"change_id": change_id, "status": "applied", "already_applied": True}
            if change["status"] != "approved":
                raise HTTPException(409, "Reviewer approval is required")
            finding = db.execute(
                "SELECT * FROM findings WHERE id=?", (change["finding_id"],)
            ).fetchone()
            payload = json.loads(finding["payload"])
            if finding["status"] != "open":
                raise HTTPException(409, "Finding is closed; investigate before applying")
            run = get_run(db, finding["run_id"])
            snapshots = json.loads(run["snapshots"])
            targets = [
                r
                for r in snapshots[payload["source"]]
                if r["worker_id"].strip() == payload["worker_id"]
            ]
            if len(targets) != 1 or targets[0][payload["field"]] != change["old_value"]:
                raise HTTPException(409, "Source changed since request; investigate again")
            _, context = run_context(db, run["id"])
            if context.get("provenance") and payload["source"] == "workday":
                raise HTTPException(422, "Imported Workday source is read-only")
            before = {
                f.signature
                for f in audit_for_context(snapshots, date.fromisoformat(run["as_of"]), context)
            }
            targets[0][payload["field"]] = change["proposed"]
            remaining = audit_for_context(snapshots, date.fromisoformat(run["as_of"]), context)
            signatures = {f.signature for f in remaining}
            target_signature = (
                payload["rule"],
                payload["worker_id"],
                payload["source"],
                payload["field"],
            )
            if target_signature in signatures or signatures - before:
                raise HTTPException(409, "Revalidation failed; no changes applied")
            db.execute("UPDATE runs SET snapshots=? WHERE id=?", (encoded(snapshots), run["id"]))
            db.execute("UPDATE findings SET status='resolved' WHERE id=?", (finding["id"],))
            db.execute("UPDATE changes SET status='applied' WHERE id=?", (change_id,))
            db.execute(
                "INSERT INTO events(change_id,actor,action) VALUES(?,?,?)",
                (change_id, role, "applied_and_revalidated"),
            )
        return {"change_id": change_id, "status": "applied", "remaining": len(remaining)}

    @app.get("/changes/{change_id}/events")
    def events(change_id: str, role: Actor):
        with store.transaction() as db:
            if db.execute("SELECT id FROM changes WHERE id=?", (change_id,)).fetchone() is None:
                raise HTTPException(404, "Change not found")
            return [
                dict(r)
                for r in db.execute(
                    "SELECT actor,action,created_at FROM events WHERE change_id=? ORDER BY id",
                    (change_id,),
                )
            ]

    @app.get("/runs/{run_id}/report.csv")
    def report(run_id: str, role: Actor):
        rows = findings(run_id, role)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        fields = ["worker_id", "rule", "source", "field", "observed", "expected", "status"]
        writer.writerow(fields)
        for row in rows:
            # Quoting alone does not prevent spreadsheet formula injection.
            values = [str(row[field]) for field in fields]
            writer.writerow(
                ["'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v for v in values]
            )
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="synthetic-audit.csv"'},
        )

    @app.get("/workday/capture", tags=["Personal Workday lab"])
    def workday_capture(role: Actor):
        try:
            return capture_summary(Path(settings.db_path).parent / "workday-probe.json")
        except (WorkdayConnectionError, OSError):
            raise HTTPException(
                422, "Workday capture unavailable or invalid; inspect local evidence"
            ) from None

    @app.get("/workday/staging", tags=["Personal Workday lab"])
    def workday_staging(role: Actor):
        return read_stage(Path(settings.db_path).parent)

    @app.post("/workday/audits", tags=["Personal Workday lab"])
    def workday_audit(role: Actor, training_errors: bool = False):
        allowed(role, "analyst")
        return import_stage(store, read_stage(Path(settings.db_path).parent), training_errors)

    register_lab(app, store, actor)
    return app
