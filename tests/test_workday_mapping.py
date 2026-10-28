import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from people_quality.api import Settings, create_app
from people_quality.operations import WorkflowError
from people_quality.workday_mapping import read_stage

ALIASES = {
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
KEYS = {r: r + "-mapping-test-" + "x" * 32 for r in ("analyst", "reviewer", "operator")}


def write_capture(folder, mutation=None):
    rows, records, probe_rows = [], [], []
    for index, (employee_id, worker_wid) in enumerate([("0007", "a" * 32), ("0008", "b" * 32)]):
        rows.append(
            {
                "employeeID": employee_id,
                "worker": {"id": worker_wid, "descriptor": "Sample worker"},
                "costCenter_ID": f"70{index + 1}",
                "costCenter": {"id": str(index + 1) * 32, "descriptor": "Sample centre"},
                "FTE": "0.5",
                "FTEPct": "50",
                "managerID": "0001",
                "manager_EffectiveDated": {"id": "c" * 32, "descriptor": "Sample manager"},
                "hireDate": "2021-01-01",
                "activeStatus": True,
                "terminated": False,
                "onLeave": False,
                "workerType": {"descriptor": "Employee"},
            }
        )
        records.append(
            {
                "workday_id": worker_wid,
                "staffing": {
                    "http_status": 200,
                    "body": {
                        "id": worker_wid,
                        "workerId": employee_id,
                        "workerType": {"descriptor": "Employee"},
                    },
                },
                "service_dates": {
                    "http_status": 200,
                    "body": {"data": [{"hireDate": "2021-01-01"}]},
                },
            }
        )
        probe_rows.append({"id": worker_wid})
    capture = {
        "sample_only": True,
        "records": records,
        "wql_data": {"http_status": 200, "body": {"data": rows}},
        "selected_fields": {
            k: {"alias": a, "type": "Test metadata type"} for k, a in ALIASES.items()
        },
        "manager_references": {
            "c" * 32: {"http_status": 200, "body": {"id": "c" * 32, "workerId": "0001"}}
        },
    }
    if mutation:
        mutation(capture)
    (folder / "workday-discovery.json").write_text(json.dumps(capture), encoding="utf-8")
    (folder / "workday-probe.json").write_text(
        json.dumps(
            {
                "sample_only": True,
                "source": "personal_workday_development_tenant",
                "mode": "read_only_api_probe",
                "audit_imported": False,
                "received_rows": len(probe_rows),
                "checked_at": "2026-10-29T01:00:00+00:00",
                "response": {"data": probe_rows},
            }
        ),
        encoding="utf-8",
    )
    return capture


def test_strict_mapping_preserves_ids_units_and_source(tmp_path):
    write_capture(tmp_path)
    stage = read_stage(tmp_path)
    assert stage["ready"] and not stage["errors"]
    assert stage["rows"][0]["worker_id"] == "0007"
    assert stage["rows"][0]["manager_id"] == "0001"
    assert stage["rows"][0]["cost_centre"] == "701"
    assert stage["rows"][0]["fte"] == 0.5
    assert stage["rows"][0]["fte_percent"] == 50
    assert stage["rows"][0]["termination_date"] == ""
    assert len(stage["source_sha256"]) == 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("FTE", "NaN"),
        ("FTEPct", "100"),
        ("managerID", "wrong"),
        ("activeStatus", "true"),
        ("employeeID", "unexpected"),
        ("hireDate", "2022-01-01"),
    ],
)
def test_bad_fields_are_quarantined_not_filled(tmp_path, field, value):
    write_capture(tmp_path, lambda c: c["wql_data"]["body"]["data"][0].update({field: value}))
    stage = read_stage(tmp_path)
    assert not stage["ready"] and stage["errors"]
    with TestClient(create_app(Settings(str(tmp_path / "test.db"), KEYS))) as api:
        assert (
            api.post("/workday/audits", headers={"X-API-Key": KEYS["analyst"]}).status_code == 422
        )
        assert api.get("/runs", headers={"X-API-Key": KEYS["analyst"]}).json() == []


def test_missing_field_and_population_mismatch(tmp_path):
    write_capture(tmp_path, lambda c: c["wql_data"]["body"]["data"][0].pop("FTE"))
    assert not read_stage(tmp_path)["ready"]
    write_capture(tmp_path, lambda c: c["wql_data"]["body"]["data"].pop())
    with pytest.raises(WorkflowError, match="one bounded WQL row"):
        read_stage(tmp_path)


def test_workday_training_reuses_review_flow_without_changing_hr(tmp_path):
    write_capture(tmp_path)
    with TestClient(create_app(Settings(str(tmp_path / "test.db"), KEYS))) as api:

        def h(role="analyst"):
            return {"X-API-Key": KEYS[role]}

        assert api.get("/workday/staging").status_code == 401
        assert api.post("/workday/audits", headers=h("operator")).status_code == 403
        clean = api.post("/workday/audits", headers=h()).json()
        assert clean["findings"] == 0
        run = api.post("/workday/audits?training_errors=true", headers=h()).json()
        assert run["findings"] == 2
        rid = run["run_id"]
        original = deepcopy(
            api.get(f"/runs/{rid}/records/0007", headers=h()).json()["sources"]["workday"]
        )
        cases = api.get(f"/runs/{rid}/findings", headers=h()).json()
        cc = next(f for f in cases if f["rule"] == "COST_CENTRE_MISMATCH")
        change = api.post(
            "/changes",
            headers=h(),
            json={
                "finding_id": cc["id"],
                "new_value": "701",
                "reason": "Confirmed original Workday capture and scoped reference code.",
            },
        ).json()["change_id"]
        assert api.post(f"/changes/{change}/apply", headers=h("operator")).status_code == 409
        api.post(f"/changes/{change}/approve", headers=h("reviewer")).raise_for_status()
        assert api.post(f"/changes/{change}/apply", headers=h("operator")).json()["remaining"] == 1
        fte = next(f for f in cases if f["rule"] == "FTE_RANGE")
        wrong = api.post(
            "/lab/batches/preview",
            headers=h(),
            json={
                "items": [{"finding_id": fte["id"], "new_value": "1.0"}],
                "reason": "Valid numeric range alone is not sufficient to match the source.",
            },
        )
        assert wrong.status_code == 409
        batch = api.post(
            "/lab/batches",
            headers=h(),
            json={
                "items": [{"finding_id": fte["id"], "new_value": "0.5"}],
                "reason": "Confirmed half-time ratio in the original source capture.",
            },
        ).json()["id"]
        api.post(
            f"/lab/batches/{batch}/approve",
            headers=h("reviewer"),
            json={"reason": "Source ratio and review are confirmed."},
        ).raise_for_status()
        result = api.post(
            f"/lab/batches/{batch}/apply",
            headers=h("operator"),
            json={"reason": "Apply to simulated downstream data only."},
        )
        assert result.status_code == 200 and result.json()["remaining"] == 0
        assert (
            api.get(f"/runs/{rid}/records/0007", headers=h()).json()["sources"]["workday"]
            == original
        )
        context = api.get(f"/lab/context/{rid}", headers=h()).json()
        assert context["provenance"]["workday_read_only"] is True
        assert len(context["provenance"]["injected_training_errors"]) == 2


def test_imported_hr_cannot_be_corrected_locally(tmp_path):
    write_capture(
        tmp_path, lambda c: c["wql_data"]["body"]["data"][0].update(FTE="1.2", FTEPct="120")
    )
    with TestClient(create_app(Settings(str(tmp_path / "test.db"), KEYS))) as api:
        headers = {"X-API-Key": KEYS["analyst"]}
        run = api.post("/workday/audits", headers=headers).json()["run_id"]
        cases = api.get(f"/runs/{run}/findings", headers=headers).json()
        case = next(f for f in cases if f["source"] == "workday")
        result = api.post(
            "/lab/batches",
            headers=headers,
            json={
                "items": [{"finding_id": case["id"], "new_value": "1.0"}],
                "reason": "This attempt must not modify the imported source.",
            },
        )
        assert result.status_code == 422 and "read-only" in result.text


def test_validated_capture_can_start_practice_from_ui(tmp_path, monkeypatch):
    from pathlib import Path
    from urllib.parse import urlsplit

    from streamlit.testing.v1 import AppTest

    write_capture(tmp_path)
    for role, value in KEYS.items():
        monkeypatch.setenv(f"{role.upper()}_KEY", value)
    with TestClient(create_app(Settings(str(tmp_path / "test.db"), KEYS))) as api:

        def transport(method, url, **kwargs):
            kwargs.pop("timeout", None)
            response = api.request(method, urlsplit(url).path, **kwargs)
            response.ok = response.is_success
            return response

        monkeypatch.setattr("requests.request", transport)
        app = AppTest.from_file(str(Path(__file__).parents[1] / "ui/app.py"), default_timeout=60)
        app.run()
        app.sidebar.selectbox[1].set_value("Workday sample data").run()
        assert not app.exception
        next(
            b for b in app.button if b.label == "Create practice audit with two downstream errors"
        ).click().run()
        assert not app.exception
        assert any("2 findings" in s.value for s in app.success)
