"""Acceptance tests for whole workflows, concurrency and evidence boundaries."""

import csv
import io
import json
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from people_quality.api import Settings, create_app
from people_quality.demo import sample_snapshots
from people_quality.store import Store

KEYS = {role: role + "-lab-test-" + "x" * 32 for role in ("analyst", "reviewer", "operator")}


@pytest.fixture
def lab(tmp_path):
    path = str(tmp_path / "lab.db")
    with TestClient(create_app(Settings(path, KEYS))) as client:
        yield client, path


def h(role="analyst"):
    return {"X-API-Key": KEYS[role]}


def start(client):
    run = client.post("/runs/demo", headers=h()).json()["run_id"]
    rows = client.get(f"/runs/{run}/findings", headers=h()).json()
    return run, {r["worker_id"]: r for r in rows}


def proposal(cases, workers=("E0035", "E0045")):
    values = {"E0003": "C100", "E0012": "1.0", "E0015": "E0001", "E0035": "C100", "E0045": "C100"}
    return {
        "items": [{"finding_id": cases[w]["id"], "new_value": values[w]} for w in workers],
        "reason": "Confirmed synthetic field owner and current approved values.",
    }


def note(**kwargs):
    return {
        "owner": "Payroll",
        "priority": "high",
        "state": "investigating",
        "root_cause": "Unknown",
        "evidence": "Comparing approved records; cause not established.",
        "next_action": "Ask payroll owner about the update",
        "due_date": "2026-10-30",
        "expected_version": 0,
        **kwargs,
    }


def test_case_assignment_escalation_concurrency_and_no_change_closure(lab):
    c, _ = lab
    run, cases = start(c)
    path = f"/lab/cases/{cases['E0035']['id']}"
    assert c.get(path, headers=h()).json()["state"] == "new"
    assert c.put(path, headers=h("reviewer"), json=note()).status_code == 403
    assert c.put(path, headers=h(), json=note()).json()["version"] == 1
    assert c.put(path, headers=h(), json=note()).status_code == 409
    assert (
        c.put(
            path,
            headers=h(),
            json=note(expected_version=1, state="escalated", owner="Workday support"),
        ).status_code
        == 200
    )
    events = c.get(f"/lab/events/{cases['E0035']['id']}", headers=h()).json()
    assert len(events) == 2
    close = note(
        expected_version=2,
        state="closed_no_change",
        evidence="Practice: owner confirms this difference is accepted for this period.",
    )
    assert c.put(path, headers=h(), json=close).status_code == 200
    assert c.get(path, headers=h()).json()["state"] == "closed_no_change"
    assert c.put(path, headers=h(), json=note(expected_version=3)).status_code == 409
    assert c.get(f"/lab/reports/{run}", headers=h()).json()["open_cases"] == 6
    assert c.get("/lab/cases/missing", headers=h()).status_code == 404
    assert c.put("/lab/cases/missing", headers=h(), json=note()).status_code == 404


@pytest.mark.parametrize(
    "action,role,expected", [("reject", "reviewer", "rejected"), ("cancel", "analyst", "cancelled")]
)
def test_single_rejection_cancellation_keep_sources_unchanged(lab, action, role, expected):
    c, _ = lab
    run, cases = start(c)
    change = c.post(
        "/changes",
        headers=h(),
        json={
            "finding_id": cases["E0035"]["id"],
            "new_value": "C100",
            "reason": "Evidence checked with synthetic HR.",
        },
    ).json()["change_id"]
    path = f"/lab/changes/{change}/{action}"
    assert (
        c.post(
            path, headers=h("operator"), json={"reason": "Do not proceed with this request."}
        ).status_code
        == 403
    )
    assert (
        c.post(path, headers=h(role), json={"reason": "Do not proceed with this request."}).json()[
            "status"
        ]
        == expected
    )
    assert (
        c.post(
            path, headers=h(role), json={"reason": "A second decision should be blocked."}
        ).status_code
        == 409
    )
    assert c.post(f"/changes/{change}/apply", headers=h("operator")).status_code == 409
    records = c.get(f"/runs/{run}/records/E0035", headers=h()).json()
    assert records["sources"]["payroll"][0]["cost_centre"] == "C200"
    assert (
        c.post(
            "/lab/changes/missing/reject",
            headers=h("reviewer"),
            json={"reason": "No such request exists."},
        ).status_code
        == 404
    )
    assert (
        c.post(
            f"/lab/changes/{change}/wrong",
            headers=h(),
            json={"reason": "Invalid action requested."},
        ).status_code
        == 404
    )


def test_full_batch_corrects_multiple_fields_only_after_review(lab):
    c, _ = lab
    run, cases = start(c)
    body = proposal(cases, ("E0003", "E0012", "E0015", "E0035", "E0045"))
    preview = c.post("/lab/batches/preview", headers=h(), json=body).json()
    assert preview["before_count"] == 7 and preview["after_count"] == 2
    assert not preview["applied"]
    assert c.get(f"/lab/reports/{run}", headers=h()).json()["open_cases"] == 7
    batch = c.post("/lab/batches", headers=h(), json=body).json()["id"]
    path = f"/lab/batches/{batch}"
    reason = {"reason": "Reviewed complete synthetic batch and dry-run results."}
    assert c.post(path + "/apply", headers=h("operator"), json=reason).status_code == 409
    assert c.post(path + "/approve", headers=h(), json=reason).status_code == 403
    assert c.post(path + "/approve", headers=h("reviewer"), json=reason).status_code == 200
    assert c.post(path + "/approve", headers=h("reviewer"), json=reason).status_code == 409
    applied = c.post(path + "/apply", headers=h("operator"), json=reason).json()
    assert applied["remaining"] == 2
    assert c.post(path + "/apply", headers=h("operator"), json=reason).json()["already_applied"]
    assert len(c.get(f"/lab/events/{batch}", headers=h()).json()) == 3
    assert c.get(f"/lab/reports/{run}", headers=h()).json()["open_cases"] == 2
    assert c.get("/lab/batches", headers=h()).json()[0]["status"] == "applied"
    assert c.get(f"/lab/cases/{cases['E0012']['id']}", headers=h()).json()["state"] == "resolved"


@pytest.mark.parametrize(
    "worker,value",
    [
        ("E0012", "NaN"),
        ("E0012", "text"),
        ("E0012", "0"),
        ("E0015", "E0015"),
        ("E0015", "E9999"),
        ("E0035", "C300"),
        ("E0035", "C999"),
        ("E0035", "C200"),
        ("E0020", "E0033"),
        ("E0050", "E0050"),
        ("E0003", "C200"),
    ],
)
def test_invalid_or_harmful_batch_preview_does_not_write(lab, worker, value):
    c, _ = lab
    run, cases = start(c)
    body = {
        "items": [{"finding_id": cases[worker]["id"], "new_value": value}],
        "reason": "Testing invalid input without saving any changes.",
    }
    response = c.post("/lab/batches/preview", headers=h(), json=body)
    assert response.status_code in (422, 409)
    assert c.get("/lab/batches", headers=h()).json() == []
    assert c.get(f"/lab/reports/{run}", headers=h()).json()["open_cases"] == 7


def test_bulk_duplicates_cross_run_missing_and_stale_are_rejected(lab):
    c, path = lab
    run, cases = start(c)
    _, other = start(c)
    body = proposal(cases, ("E0035",))
    body["items"] *= 2
    assert c.post("/lab/batches/preview", headers=h(), json=body).status_code == 422
    body["items"][1] = proposal(other, ("E0045",))["items"][0]
    assert c.post("/lab/batches/preview", headers=h(), json=body).status_code == 422
    body["items"] = [{"finding_id": "missing", "new_value": "C100"}]
    assert c.post("/lab/batches/preview", headers=h(), json=body).status_code == 404
    with Store(path).transaction() as db:
        row = db.execute("SELECT snapshots FROM runs WHERE id=?", (run,)).fetchone()
        records = json.loads(row[0])
        records["payroll"][34]["cost_centre"] = "C300"
        db.execute("UPDATE runs SET snapshots=? WHERE id=?", (json.dumps(records), run))
    assert c.post("/lab/batches/preview", headers=h(), json=proposal(cases)).status_code == 409


def test_stale_second_row_rolls_back_entire_approved_batch(lab):
    c, path = lab
    run, cases = start(c)
    batch = c.post("/lab/batches", headers=h(), json=proposal(cases)).json()["id"]
    reason = {"reason": "Reviewed synthetic source values and batch impact."}
    c.post(f"/lab/batches/{batch}/approve", headers=h("reviewer"), json=reason)
    with Store(path).transaction() as db:
        records = json.loads(
            db.execute("SELECT snapshots FROM runs WHERE id=?", (run,)).fetchone()[0]
        )
        records["core"][44]["cost_centre"] = "C200"
        db.execute("UPDATE runs SET snapshots=? WHERE id=?", (json.dumps(records), run))
    result = c.post(f"/lab/batches/{batch}/apply", headers=h("operator"), json=reason)
    assert result.status_code == 409
    assert (
        c.get(f"/runs/{run}/records/E0035", headers=h()).json()["sources"]["payroll"][0][
            "cost_centre"
        ]
        == "C200"
    )
    assert c.get("/lab/batches", headers=h()).json()[0]["status"] == "approved"
    assert len(c.get(f"/lab/events/{batch}", headers=h()).json()) == 2
    assert c.post(f"/lab/batches/{batch}/cancel", headers=h(), json=reason).status_code == 200
    assert c.get("/lab/batches", headers=h()).json()[0]["reviewed_by"] == "reviewer"


@pytest.mark.parametrize(
    "action,role,state", [("reject", "reviewer", "rejected"), ("cancel", "analyst", "cancelled")]
)
def test_batch_rejection_cancellation_and_missing_routes(lab, action, role, state):
    c, _ = lab
    _, cases = start(c)
    batch = c.post("/lab/batches", headers=h(), json=proposal(cases)).json()["id"]
    reason = {"reason": "Do not proceed until the owner confirms this."}
    assert (
        c.post(f"/lab/batches/{batch}/{action}", headers=h(role), json=reason).json()["status"]
        == state
    )
    assert (
        c.post(f"/lab/batches/{batch}/apply", headers=h("operator"), json=reason).status_code == 409
    )
    assert (
        c.post("/lab/batches/missing/approve", headers=h("reviewer"), json=reason).status_code
        == 404
    )
    assert (
        c.post("/lab/batches/missing/apply", headers=h("operator"), json=reason).status_code == 404
    )
    assert c.post(f"/lab/batches/{batch}/wrong", headers=h(), json=reason).status_code == 404


def test_date_alignment_reports_history_and_legacy_context(lab):
    c, path = lab
    run, cases = start(c)
    assert (
        c.get(f"/lab/reports/{run}", headers=h(), params={"source": "payroll"}).json()["open_cases"]
        == 2
    )
    assert (
        c.get(
            f"/lab/reports/{run}", headers=h(), params={"rule": "FTE_RANGE", "status": "open"}
        ).json()["filtered_cases"]
        == 1
    )
    assert c.get("/lab/context/missing", headers=h()).status_code == 404
    context = c.get(f"/lab/context/{run}", headers=h()).json()
    assert context["capture_kind"] == "original_import" and "captured_snapshot" not in context
    with Store(path).transaction() as db:
        db.execute("DELETE FROM run_context WHERE run_id=?", (run,))
    assert (
        c.get(f"/lab/context/{run}", headers=h()).json()["capture_kind"]
        == "migration_current_state"
    )
    timed = c.post("/lab/timing-scenario", headers=h()).json()["run_id"]
    report = c.get(f"/lab/reports/{timed}", headers=h()).json()
    assert report["by_rule"]["SNAPSHOT_DATE"] == 1
    target = next(r for r in report["rows"] if r["worker_id"] == "E0045")
    body = {
        "items": [{"finding_id": target["id"], "new_value": "C100"}],
        "reason": "Testing source-date gate on a correction.",
    }
    assert c.post("/lab/batches/preview", headers=h(), json=body).status_code == 422
    assert (
        c.post(
            "/changes",
            headers=h(),
            json={
                "finding_id": target["id"],
                "new_value": "C100",
                "reason": "Testing the same date gate for single changes.",
            },
        ).status_code
        == 422
    )
    history = c.post("/lab/practice-history", headers=h()).json()["runs"]
    assert [r["findings"] for r in history] == [7, 6, 5]
    groups = c.get("/lab/trends", headers=h()).json()["groups"]
    assert any(len(g["points"]) == 3 for g in groups if "history-practice" in g["cohort"])
    assert any(not p["comparable"] for g in groups for p in g["points"])
    payload = {
        "as_of": "2026-10-29",
        **sample_snapshots(),
        "source_dates": {"workday": "2026-10-29"},
    }
    assert c.post("/runs", headers=h(), json=payload).status_code == 422
    payload.pop("source_dates")
    payload["workday"][0]["status"] = "unmapped"
    assert c.post("/runs", headers=h(), json=payload).status_code == 422


def test_knowledge_versions_search_and_coaching_evidence(lab):
    c, _ = lab
    articles = c.get("/lab/articles", headers=h(), params={"q": "payroll"}).json()
    assert articles
    article = articles[0]
    body = {k: article[k] for k in ("title", "audience", "body", "review_date")}
    body.update(
        body=article["body"] + " Confirm effective dates before taking action.", expected_version=1
    )
    assert c.put(f"/lab/articles/{article['id']}", headers=h(), json=body).json()["version"] == 2
    assert c.put(f"/lab/articles/{article['id']}", headers=h(), json=body).status_code == 409
    versions = c.get(f"/lab/documents/article/{article['id']}/versions", headers=h()).json()
    assert len(versions) == 2 and versions[0]["body"] != versions[1]["body"]
    session = {
        "evidence_kind": "self_practice",
        "learner_alias": "Practice learner",
        "question": "timing",
        "answer": "I should compare the same dates before changing a field.",
        "feedback": "Good date check; also confirm the population and owner.",
    }
    assert c.post("/lab/coaching", headers=h(), json=session).status_code == 200
    coaching = c.get("/lab/coaching", headers=h()).json()
    assert (
        len(coaching["prompts"]) == 3
        and coaching["sessions"][0]["evidence_kind"] == "self_practice"
    )


def test_requirements_review_and_optimistic_versioning(lab):
    c, _ = lab
    body = {
        "title": "Show reporting period before correction",
        "team": "Payroll",
        "business_problem": "Different extract dates can lead to wrong corrections.",
        "acceptance_criteria": "Given different dates, when previewed, then block correction.",
        "decision": "Agree a current reporting date with the source owner.",
        "evidence_kind": "self_practice",
        "expected_version": 0,
    }
    assert c.put("/lab/requirements/date-check", headers=h(), json=body).status_code == 200
    review = {
        "reason": "Acceptance criteria are testable and ownership is clear.",
        "expected_version": 1,
    }
    assert (
        c.post("/lab/requirements/date-check/accept", headers=h(), json=review).status_code == 403
    )
    assert (
        c.post("/lab/requirements/date-check/accept", headers=h("reviewer"), json=review).json()[
            "status"
        ]
        == "accepted"
    )
    assert (
        c.post(
            "/lab/requirements/date-check/accept", headers=h("reviewer"), json=review
        ).status_code
        == 409
    )
    assert (
        c.post("/lab/requirements/missing/accept", headers=h("reviewer"), json=review).status_code
        == 404
    )
    assert c.get("/lab/requirements", headers=h()).json()[0]["version"] == 2


def test_failed_release_defect_retest_and_reviewed_closure(lab):
    c, _ = lab
    bad = c.post("/lab/test-runs", headers=h(), json={"release": "candidate_bug"}).json()
    assert not bad["passed"]
    failed = [r for r in bad["results"] if not r["passed"]]
    assert [r["name"] for r in failed] == ["paid_leave"]
    defect = {
        "test_run_id": bad["id"],
        "case_name": "paid_leave",
        "impact": "Valid paid-leave employees would be wrongly flagged.",
        "steps": "Run the candidate_bug release and inspect the paid_leave acceptance case.",
    }
    record = c.post("/lab/defects", headers=h(), json=defect).json()
    assert record["status"] == "open" and record["actual"] == ["LEAVE_PAYROLL_ERROR"]
    invalid = {**defect, "case_name": "valid_records"}
    assert c.post("/lab/defects", headers=h(), json=invalid).status_code == 422
    assert (
        c.post("/lab/defects", headers=h(), json={**defect, "test_run_id": "missing"}).status_code
        == 404
    )
    resolution = {
        "passing_test_run_id": bad["id"],
        "reason": "Check the complete retest evidence.",
        "expected_version": 1,
    }
    url = f"/lab/defects/{record['id']}/resolve"
    assert c.post(url, headers=h("reviewer"), json=resolution).status_code == 409
    good = c.post("/lab/test-runs", headers=h(), json={"release": "candidate_fixed"}).json()
    assert good["passed"]
    assert c.post("/lab/test-runs", headers=h(), json={"release": "stable"}).json()["passed"]
    resolution["passing_test_run_id"] = good["id"]
    assert c.post(url, headers=h(), json=resolution).status_code == 403
    assert c.post(url, headers=h("reviewer"), json=resolution).json()["status"] == "resolved"
    assert c.post(url, headers=h("reviewer"), json=resolution).status_code == 409
    assert (
        c.post("/lab/defects/missing/resolve", headers=h("reviewer"), json=resolution).status_code
        == 404
    )
    assert c.get("/lab/defects", headers=h()).json()[0]["passing_test_run_id"] == good["id"]
    assert len(c.get("/lab/test-runs", headers=h()).json()) == 3


def test_pending_changes_block_case_closure(lab):
    c, _ = lab
    _, cases = start(c)
    finding = cases["E0035"]["id"]
    batch = c.post("/lab/batches", headers=h(), json=proposal(cases)).json()["id"]
    assert (
        c.put(f"/lab/cases/{finding}", headers=h(), json=note(state="closed_no_change")).status_code
        == 409
    )
    c.post(
        f"/lab/batches/{batch}/cancel",
        headers=h(),
        json={"reason": "Withdraw the unconfirmed proposal."},
    )
    c.post(
        "/changes",
        headers=h(),
        json={
            "finding_id": finding,
            "new_value": "C100",
            "reason": "Waiting for source owner confirmation.",
        },
    )
    assert (
        c.put(f"/lab/cases/{finding}", headers=h(), json=note(state="closed_no_change")).status_code
        == 409
    )


def test_excel_export_preserves_captured_and_current_snapshots(lab):
    c, _ = lab
    run, cases = start(c)
    change = c.post(
        "/changes",
        headers=h(),
        json={
            "finding_id": cases["E0035"]["id"],
            "new_value": "C100",
            "reason": "Compare original and corrected synthetic exports.",
        },
    ).json()["change_id"]
    c.post(f"/changes/{change}/approve", headers=h("reviewer"))
    c.post(f"/changes/{change}/apply", headers=h("operator"))
    for view, expected in [("captured", "C200"), ("current", "C100")]:
        response = c.get(f"/lab/exports/{run}.zip", headers=h(), params={"view": view})
        with ZipFile(io.BytesIO(response.content)) as archive:
            rows = list(csv.DictReader(io.StringIO(archive.read("payroll.csv").decode())))
            assert next(r for r in rows if r["worker_id"] == "E0035")["cost_centre"] == expected
            assert json.loads(archive.read("manifest.json"))["synthetic_only"]
            assert (
                len(list(csv.DictReader(io.StringIO(archive.read("workday.csv").decode())))) == 101
            )
