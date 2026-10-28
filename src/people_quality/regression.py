"""Executable business acceptance scenarios for fictional releases of this app."""

from copy import deepcopy
from dataclasses import asdict
from datetime import date

from people_quality.domain import SOURCES, Finding, audit


def base_records():
    workers = [
        {
            "worker_id": f"E{i:04}",
            "worker_type": "Employee",
            "status": "Active",
            "cost_centre": "C100",
            "manager_id": "" if i == 1 else "E0001",
            "fte": 1.0,
            "hire_date": "2026-01-01",
            "termination_date": "",
        }
        for i in range(1, 4)
    ]
    return {source: deepcopy(workers) for source in SOURCES}


def suite(release):
    specs = [
        ("valid_records", "Valid records have no findings", "none", []),
        (
            "cost_centre",
            "Different payroll cost centre is flagged",
            "cost",
            ["COST_CENTRE_MISMATCH"],
        ),
        (
            "duplicate",
            "Duplicate ID is flagged without creating a false missing-worker case",
            "duplicate",
            ["DUPLICATE_ID"],
        ),
        ("future_hire", "A future hire may be absent from today's payroll", "future", []),
        ("contingent", "A contingent worker may be excluded from payroll", "contingent", []),
        ("paid_leave", "Paid leave is not automatically a payroll error", "leave", []),
        ("final_pay", "Final pay needs context, not automatic status correction", "final", []),
        ("fte", "Invalid FTE is flagged", "fte", ["FTE_RANGE"]),
    ]
    results = []
    for name, description, mutation, expected in specs:
        snapshots = base_records()
        if mutation == "cost":
            snapshots["payroll"][1]["cost_centre"] = "C200"
        elif mutation == "duplicate":
            snapshots["workday"].append(deepcopy(snapshots["workday"][1]))
        elif mutation in ("future", "contingent"):
            snapshots["payroll"].pop(1)
            if mutation == "future":
                snapshots["workday"][1]["hire_date"] = "2026-11-01"
            else:
                snapshots["workday"][1]["worker_type"] = "Contingent"
        elif mutation == "leave":
            snapshots["workday"][1]["status"] = "Leave"
        elif mutation == "final":
            snapshots["workday"][1].update(status="Terminated", termination_date="2026-10-20")
        elif mutation == "fte":
            snapshots["workday"][1]["fte"] = 1.2
        findings = audit(snapshots, date(2026, 10, 29))
        if release == "candidate_bug":
            for row in snapshots["workday"]:
                if row["status"] == "Leave":
                    findings.append(
                        Finding(
                            "LEAVE_PAYROLL_ERROR",
                            row["worker_id"],
                            "payroll",
                            "status",
                            "Active",
                            "Inactive",
                            "Deliberately faulty candidate release rule.",
                        )
                    )
        actual = sorted(f.rule for f in findings)
        results.append(
            {
                "name": name,
                "description": description,
                "expected": sorted(expected),
                "actual": actual,
                "passed": actual == sorted(expected),
                "evidence": [asdict(f) for f in findings],
            }
        )
    return {
        "release": release,
        "results": results,
        "passed": all(r["passed"] for r in results),
        "scope": "Synthetic application tests, not a Workday release test",
    }
