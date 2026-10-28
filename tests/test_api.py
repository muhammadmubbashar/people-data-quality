import json

import pytest
from fastapi.testclient import TestClient

from people_quality.api import Settings, create_app
from people_quality.demo import sample_snapshots
from people_quality.store import Store

KEYS = {role: role + "-test-key-" + "x" * 32 for role in ("analyst", "reviewer", "operator")}


def headers(role="analyst"):
    return {"X-API-Key": KEYS[role]}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(str(tmp_path / "test.db"), KEYS))) as test_client:
        yield test_client


def setup_case(client):
    run = client.post("/runs/demo", headers=headers()).json()["run_id"]
    cases = client.get(f"/runs/{run}/findings", headers=headers()).json()
    case = next(f for f in cases if f["worker_id"] == "E0035")
    return run, case


def request(client, case, value="C100"):
    return client.post(
        "/changes",
        headers=headers(),
        json={
            "finding_id": case["id"],
            "new_value": value,
            "reason": "Verified current synthetic HR cost-centre record.",
        },
    )


def test_authentication_and_spoofed_role_are_rejected(client):
    assert client.get("/health").json()["mode"] == "synthetic-demo"
    assert client.get("/runs").status_code == 401
    assert client.get("/runs", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/runs/demo", headers=headers("reviewer")).status_code == 403
    assert client.post("/runs/demo", headers={"X-Role": "analyst"}).status_code == 401


def test_full_approval_apply_revalidation_and_idempotence(client):
    run, case = setup_case(client)
    change = request(client, case).json()["change_id"]
    assert client.post(f"/changes/{change}/apply", headers=headers("operator")).status_code == 409
    assert client.post(f"/changes/{change}/approve", headers=headers()).status_code == 403
    assert client.post(f"/changes/{change}/approve", headers=headers("reviewer")).status_code == 200
    assert client.post(f"/changes/{change}/approve", headers=headers("reviewer")).status_code == 409
    assert client.post(f"/changes/{change}/apply", headers=headers()).status_code == 403
    applied = client.post(f"/changes/{change}/apply", headers=headers("operator"))
    assert applied.json()["remaining"] == 6
    assert client.post(f"/changes/{change}/apply", headers=headers("operator")).json()[
        "already_applied"
    ]
    events = client.get(f"/changes/{change}/events", headers=headers()).json()
    assert [e["action"] for e in events] == ["requested", "approved", "applied_and_revalidated"]
    assert request(client, case).status_code == 409
    records = client.get(f"/runs/{run}/records/E0035", headers=headers()).json()
    assert records["sources"]["payroll"][0]["cost_centre"] == "C100"
    cases = client.get(f"/runs/{run}/findings", headers=headers()).json()
    assert next(f for f in cases if f["id"] == case["id"])["status"] == "resolved"
    assert len(client.get("/changes", headers=headers()).json()) == 1


def test_dry_run_invalid_and_duplicate_targets_block_batch_without_writes(client):
    _, case = setup_case(client)
    row = {"finding_id": case["id"], "new_value": "C100", "reason": "Evidence checked."}
    good = client.post("/changes/dry-run", headers=headers(), json={"changes": [row]}).json()
    assert good["valid"] and not good["applied"]
    duplicate = client.post("/changes/dry-run", headers=headers(), json={"changes": [row, row]})
    assert not duplicate.json()["valid"]
    invalid = {**row, "new_value": "C999"}
    assert not client.post(
        "/changes/dry-run", headers=headers(), json={"changes": [invalid]}
    ).json()["valid"]
    assert client.get("/changes", headers=headers()).json() == []


def test_invalid_change_and_unknown_resources(client):
    run, case = setup_case(client)
    assert request(client, case, "C999").status_code == 422
    assert request(client, case, "C200").status_code == 422
    assert request(client, case, "C300").status_code == 422
    assert request(client, {"id": "missing"}).status_code == 404
    cases = client.get(f"/runs/{run}/findings", headers=headers()).json()
    fte = next(f for f in cases if f["rule"] == "FTE_RANGE")
    assert request(client, fte).status_code == 422
    assert client.get("/runs/missing/findings", headers=headers()).status_code == 404
    assert client.get("/changes/missing/events", headers=headers()).status_code == 404
    assert client.post("/changes/missing/approve", headers=headers("reviewer")).status_code == 404
    assert client.post("/changes/missing/apply", headers=headers("operator")).status_code == 404
    assert client.get("/runs", headers=headers()).json()[0]["id"] == run


def test_new_run_schema_and_csv_injection_protection(client):
    snapshots = sample_snapshots()
    for row in snapshots["workday"][-2:]:
        row["worker_id"] = "=1+1"
    response = client.post("/runs", headers=headers(), json={"as_of": "2026-10-29", **snapshots})
    assert response.status_code == 200
    report = client.get(f"/runs/{response.json()['run_id']}/report.csv", headers=headers())
    assert "'=1+1" in report.text
    assert client.post("/runs", headers=headers(), json={"as_of": "bad"}).status_code == 422


def test_stale_source_is_rejected_without_event_or_state_change(tmp_path):
    path = str(tmp_path / "test.db")
    with TestClient(create_app(Settings(path, KEYS))) as client:
        run, case = setup_case(client)
        change = request(client, case).json()["change_id"]
        client.post(f"/changes/{change}/approve", headers=headers("reviewer"))
        with Store(path).transaction() as db:
            row = db.execute("SELECT snapshots FROM runs WHERE id=?", (run,)).fetchone()
            snapshots = json.loads(row["snapshots"])
            snapshots["payroll"][34]["cost_centre"] = "C300"
            db.execute("UPDATE runs SET snapshots=? WHERE id=?", (json.dumps(snapshots), run))
        assert (
            client.post(f"/changes/{change}/apply", headers=headers("operator")).status_code == 409
        )
        assert len(client.get(f"/changes/{change}/events", headers=headers()).json()) == 2


def test_configuration_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match="Production"):
        create_app(Settings(str(tmp_path / "a.db"), KEYS, "production"))
    with pytest.raises(RuntimeError, match="three"):
        create_app(Settings(str(tmp_path / "b.db"), {}))
    with pytest.raises(RuntimeError, match="random"):
        create_app(Settings(str(tmp_path / "c.db"), dict.fromkeys(KEYS, "short")))


def test_unknown_schema_is_not_silently_overwritten(tmp_path):
    path = str(tmp_path / "schema.db")
    with Store(path).transaction() as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="migration"):
        Store(path)
