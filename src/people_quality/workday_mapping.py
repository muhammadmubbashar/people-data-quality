"""Strict mapping of verified WQL sample captures into the local audit contract."""

import hashlib
import json
import re
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from people_quality.domain import Worker
from people_quality.operations import WorkflowError, create_run


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ValueError(f"Missing or invalid {name}")
    return value.strip()


def wid(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Invalid Workday internal ID")
    return value


def read_stage(folder):
    path = folder / "workday-discovery.json"
    probe_path = folder / "workday-probe.json"
    if not path.exists() or not probe_path.exists():
        return {"status": "not_captured", "ready": False, "rows": [], "errors": []}
    if path.stat().st_size > 8_000_000 or probe_path.stat().st_size > 2_000_000:
        raise WorkflowError("Workday evidence exceeds the staging size limit")
    try:
        raw = path.read_bytes()
        data, probe = json.loads(raw), json.loads(probe_path.read_bytes())
        if data["sample_only"] is not True or probe["sample_only"] is not True:
            raise ValueError("Only personal development sample captures are supported")
        captured = datetime.fromisoformat(probe["checked_at"])
        if captured.tzinfo is None:
            raise ValueError("Capture needs an explicit timezone")
        as_of = captured.astimezone(ZoneInfo("Australia/Brisbane")).date()
        if data["wql_data"]["http_status"] != 200:
            raise ValueError("No successful WQL worker capture")
        source_rows = data["wql_data"]["body"]["data"]
        records = data["records"]
        if not isinstance(source_rows, list) or any(not isinstance(r, dict) for r in source_rows):
            raise ValueError("WQL rows must be structured records")
        if not 1 <= len(source_rows) <= 5 or len(records) != len(source_rows):
            raise ValueError("Expected one bounded WQL row per captured sample worker")
        expected = {}
        for r in records:
            if r["staffing"]["http_status"] != 200 or r["service_dates"]["http_status"] != 200:
                raise ValueError("Staffing and service dates must be verified")
            body = r["staffing"]["body"]
            employee_id = text(body["workerId"], "employee number")
            if employee_id in expected:
                raise ValueError("Duplicate employee number in Staffing capture")
            if body["id"] != r["workday_id"]:
                raise ValueError("Staffing internal ID differs from captured worker")
            expected[employee_id] = r
        probe_ids = {wid(r["id"]) for r in probe["response"]["data"]}
        if probe_ids != {r["workday_id"] for r in records}:
            raise ValueError("Worker-list and enrichment captures cover different workers")
        required_aliases = {
            "employee_id": "employeeID",
            "worker": "worker",
            "cost_centre": "costCenter",
            "cost_centre_id": "costCenter_ID",
            "fte": "FTE",
            "fte_percent": "FTEPct",
            "manager_id": "managerID",
            "manager": "manager_EffectiveDated",
            "hire_date": "hireDate",
            "active": "activeStatus",
            "terminated": "terminated",
            "on_leave": "onLeave",
            "termination_date": "terminationDate",
            "worker_type": "workerType",
        }
        for key, alias in required_aliases.items():
            if data["selected_fields"][key]["alias"] != alias:
                raise ValueError("Unverified field mapping")
        field_map = {
            k: {"alias": v["alias"], "type": v["type"]} for k, v in data["selected_fields"].items()
        }
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WorkflowError(f"Workday staging blocked: {exc}") from None
    rows, errors, seen = [], [], set()
    for index, row in enumerate(source_rows):
        employee_id = row.get("employeeID", f"row-{index + 1}")
        try:
            employee_id = text(employee_id, "employee number")
            if employee_id in seen or employee_id not in expected:
                raise ValueError("Duplicate or unexpected employee number in WQL capture")
            seen.add(employee_id)
            source = expected[employee_id]
            worker_wid = wid(row["worker"]["id"])
            if worker_wid != source["workday_id"]:
                raise ValueError("Employee number does not match its original Workday internal ID")
            centre = text(row["costCenter_ID"], "cost-centre reference code")
            centre_wid = wid(row["costCenter"]["id"])
            fte, percent = Decimal(row["FTE"]), Decimal(row["FTEPct"])
            if (
                not fte.is_finite()
                or not percent.is_finite()
                or abs(fte * 100 - percent) > Decimal("0.000001")
            ):
                raise ValueError("FTE ratio and FTE percentage are missing or inconsistent")
            flags = [row[k] for k in ("activeStatus", "terminated", "onLeave")]
            if any(type(v) is not bool for v in flags):
                raise ValueError("Employment status flags must be explicit booleans")
            active, terminated, on_leave = flags
            hired = date.fromisoformat(row["hireDate"])
            service_dates = source["service_dates"]["body"]["data"]
            if len(service_dates) != 1 or service_dates[0]["hireDate"] != hired.isoformat():
                raise ValueError("WQL and Staffing service dates disagree")
            if (
                row["workerType"]["descriptor"]
                != source["staffing"]["body"]["workerType"]["descriptor"]
            ):
                raise ValueError("WQL and Staffing employee types disagree")
            worker_type = {"Employee": "Employee", "Contingent Worker": "Contingent"}[
                row["workerType"]["descriptor"]
            ]
            if terminated and (active or on_leave):
                raise ValueError("Ambiguous employment status requires investigation")
            if terminated:
                status, ended = "Terminated", date.fromisoformat(row["terminationDate"]).isoformat()
            elif hired > as_of and not active and not on_leave:
                status, ended = "PreHire", ""
            elif active:
                status, ended = "Leave" if on_leave else "Active", ""
                if row.get("terminationDate"):
                    raise ValueError("Future or unexpected termination date needs explicit mapping")
            else:
                raise ValueError("Unsupported inactive employment state")
            manager_id = text(row["managerID"], "manager employee number")
            manager_wid = wid(row["manager_EffectiveDated"]["id"])
            manager = data["manager_references"][manager_wid]
            if (
                manager["http_status"] != 200
                or manager["body"]["workerId"] != manager_id
                or manager["body"]["id"] != manager_wid
            ):
                raise ValueError(
                    "Manager internal ID and employee number are not independently resolved"
                )
            canonical = Worker.model_validate(
                {
                    "worker_id": employee_id,
                    "worker_type": worker_type,
                    "status": status,
                    "cost_centre": centre,
                    "manager_id": manager_id,
                    "fte": float(fte),
                    "hire_date": hired.isoformat(),
                    "termination_date": ended,
                }
            ).model_dump()
            rows.append(
                {
                    **canonical,
                    "workday_id": worker_wid,
                    "sample_worker": row["worker"].get("descriptor", ""),
                    "cost_centre_name": row["costCenter"]["descriptor"],
                    "cost_centre_wid": centre_wid,
                    "manager_name": row["manager_EffectiveDated"]["descriptor"],
                    "fte_percent": float(percent),
                    "manager_workday_id": manager_wid,
                }
            )
        except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError) as exc:
            errors.append({"employee_id": str(employee_id), "reason": str(exc)})
    if seen != set(expected):
        errors.append({"employee_id": "ALL", "reason": "The WQL population is incomplete"})
    return {
        "status": "validated" if not errors else "quarantined",
        "ready": not errors,
        "rows": rows,
        "errors": errors,
        "as_of": as_of.isoformat(),
        "captured_at": captured.isoformat(),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "field_map": field_map,
        "coverage": [
            "Five-worker sample, current tenant state; no historical effective-date claim.",
            "Cost-centre codes are resolved assignments in this capture, "
            "not the full active finance master.",
            "Manager references were resolved through Staffing; "
            "managers are outside the five-row audit population.",
            "Payroll and Core datasets are practice copies, never live employer sources.",
        ],
    }


def import_stage(store, stage, training_errors=False):
    if not stage.get("ready") or not stage.get("rows"):
        raise WorkflowError("Resolve every staging error before importing")
    fields = set(Worker.model_fields)
    hr = [{k: v for k, v in r.items() if k in fields} for r in stage["rows"]]
    snapshots = {name: deepcopy(hr) for name in ("workday", "payroll", "core")}
    injected = []
    if training_errors:
        codes = sorted({r["cost_centre"] for r in hr})
        if len(hr) < 2 or len(codes) < 2:
            raise WorkflowError("Training needs two workers and two captured cost centres")
        old = snapshots["payroll"][0]["cost_centre"]
        new = next(c for c in codes if c != old)
        snapshots["payroll"][0]["cost_centre"] = new
        snapshots["core"][1]["fte"] = 1.2
        injected = [
            {
                "worker_id": hr[0]["worker_id"],
                "source": "payroll",
                "field": "cost_centre",
                "old": old,
                "new": new,
            },
            {
                "worker_id": hr[1]["worker_id"],
                "source": "core",
                "field": "fte",
                "old": hr[1]["fte"],
                "new": 1.2,
            },
        ]
    provenance = {k: stage[k] for k in ("source_sha256", "captured_at", "field_map", "coverage")}
    provenance.update(
        source="personal_workday_sample",
        workday_read_only=True,
        downstream_sources="simulated copies",
        injected_training_errors=injected,
        employee_to_workday_id={r["worker_id"]: r["workday_id"] for r in stage["rows"]},
    )
    policy = {
        "cost_centres": sorted({r["cost_centre"] for r in hr}),
        "manager_reference_ids": sorted({r["manager_id"] for r in hr}),
        "compare_fte": True,
    }
    return create_run(
        store,
        snapshots,
        date.fromisoformat(stage["as_of"]),
        cohort="workday-sample-training" if training_errors else "workday-sample-clean",
        provenance=provenance,
        audit_policy=policy,
    )
