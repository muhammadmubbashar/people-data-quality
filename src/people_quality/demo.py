"""Deterministic fictional fixtures. No real employee or employer data."""

from copy import deepcopy


def sample_snapshots() -> dict[str, list[dict]]:
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
        for i in range(1, 101)
    ]
    # Legitimate exclusions: not every HR worker belongs in current payroll.
    workers[79]["worker_type"] = "Contingent"
    workers[89]["hire_date"] = "2026-11-01"
    workers[59]["status"] = "Leave"
    workers[29].update(status="Terminated", termination_date="2026-10-20")
    snapshots = {source: deepcopy(workers) for source in ("workday", "payroll", "core")}
    snapshots["workday"][2]["cost_centre"] = ""
    snapshots["workday"][11]["fte"] = 1.2
    snapshots["workday"][14]["manager_id"] = "E9999"
    snapshots["workday"].append(deepcopy(workers[19]))
    snapshots["payroll"][34]["cost_centre"] = "C200"
    snapshots["core"][44]["cost_centre"] = "C300"
    snapshots["payroll"] = [
        row for row in snapshots["payroll"] if row["worker_id"] not in {"E0050", "E0080", "E0090"}
    ]
    # A final-pay case is not automatically a bad active payroll status.
    snapshots["payroll"][29]["status"] = "Active"
    return snapshots
