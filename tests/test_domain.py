from copy import deepcopy
from datetime import date

from people_quality.demo import sample_snapshots
from people_quality.domain import audit

AS_OF = date(2026, 10, 29)


def test_demo_has_expected_findings_and_valid_exclusions():
    result = audit(sample_snapshots(), AS_OF)
    assert len(result) == 7
    assert {f.rule for f in result} == {
        "DUPLICATE_ID",
        "INVALID_COST_CENTRE",
        "FTE_RANGE",
        "MANAGER_REFERENCE",
        "COST_CENTRE_MISMATCH",
        "MISSING_WORKER",
    }
    assert not {"E0030", "E0060", "E0080", "E0090", "E0020"} & {
        f.worker_id for f in result if f.rule != "DUPLICATE_ID"
    }


def test_audit_does_not_mutate_input():
    snapshots = sample_snapshots()
    original = deepcopy(snapshots)
    audit(snapshots, AS_OF)
    assert snapshots == original


def test_dates_self_manager_missing_id_and_zero_fte():
    snapshots = sample_snapshots()
    snapshots["workday"][4]["termination_date"] = "2025-01-01"
    snapshots["workday"][5]["hire_date"] = "bad-date"
    snapshots["workday"][6]["manager_id"] = "E0007"
    snapshots["workday"][7]["fte"] = 0.0
    snapshots["core"][8]["worker_id"] = " "
    result = audit(snapshots, AS_OF)
    assert sum(f.rule == "DATE_SEQUENCE" for f in result) == 2
    assert any(f.rule == "MANAGER_REFERENCE" and f.worker_id == "E0007" for f in result)
    assert any(f.rule == "MISSING_ID" for f in result)
    assert any(f.rule == "FTE_RANGE" and f.worker_id == "E0008" for f in result)


def test_whitespace_is_normalised_for_join_without_losing_leading_zeroes():
    snapshots = sample_snapshots()
    snapshots["payroll"][1]["worker_id"] = " E0002 "
    assert not any(f.worker_id == "E0002" for f in audit(snapshots, AS_OF))
