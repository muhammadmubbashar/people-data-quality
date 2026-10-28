"""Pure audit rules. No database or web framework dependencies."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

COST_CENTRES = {"C100", "C200", "C300"}
SOURCES = ("workday", "payroll", "core")


class Worker(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    worker_id: str = Field(min_length=1, max_length=30)
    worker_type: Literal["Employee", "Contingent"] = "Employee"
    status: Literal["Active", "Leave", "Terminated", "PreHire"] = "Active"
    cost_centre: str = "C100"
    manager_id: str = "E0001"
    fte: float = 1.0
    hire_date: str = "2026-01-01"
    termination_date: str = ""


@dataclass(frozen=True)
class Finding:
    rule: str
    worker_id: str
    source: str
    field: str
    observed: str
    expected: str
    explanation: str
    severity: str = "medium"

    @property
    def signature(self) -> tuple[str, str, str, str]:
        return self.rule, self.worker_id, self.source, self.field


def audit(
    snapshots: dict[str, list[dict]], as_of: date, source_dates: dict[str, str] | None = None
) -> list[Finding]:
    """Mock policy: current AU employee extracts, three allowed cost centres.

    Duplicate keys are quarantined from joins. Payroll status is not assumed to
    equal HR status: final pay and paid leave require contextual investigation.
    """
    findings = []
    stale = set()
    if source_dates:
        for source in SOURCES:
            if source_dates[source] != as_of.isoformat():
                stale.add(source)
                findings.append(
                    Finding(
                        "SNAPSHOT_DATE",
                        "ALL",
                        source,
                        "source_date",
                        source_dates[source],
                        as_of.isoformat(),
                        "This source represents a different date. Get a comparable extract before "
                        "cross-system corrections.",
                        "high",
                    )
                )
    indexed = {}
    for source in SOURCES:
        rows = snapshots[source]
        counts = Counter(row["worker_id"].strip() for row in rows)
        indexed[source] = {
            row["worker_id"].strip(): row for row in rows if counts[row["worker_id"].strip()] == 1
        }
        for worker_id, count in counts.items():
            if count > 1:
                findings.append(
                    Finding(
                        "DUPLICATE_ID",
                        worker_id,
                        source,
                        "worker_id",
                        str(count),
                        "1",
                        "Multiple records share this ID. Resolve source ownership before joining.",
                        "high",
                    )
                )
        for worker_id, row in indexed[source].items():
            if not worker_id:
                findings.append(
                    Finding(
                        "MISSING_ID",
                        worker_id,
                        source,
                        "worker_id",
                        "",
                        "nonblank",
                        "A blank ID cannot be reliably matched across systems.",
                        "high",
                    )
                )
            if row["cost_centre"] not in COST_CENTRES:
                findings.append(
                    Finding(
                        "INVALID_COST_CENTRE",
                        worker_id,
                        source,
                        "cost_centre",
                        row["cost_centre"],
                        "C100/C200/C300",
                        "Confirm the approved cost centre with HR. Do not guess a replacement.",
                    )
                )
            if not 0 < row["fte"] <= 1:
                findings.append(
                    Finding(
                        "FTE_RANGE",
                        worker_id,
                        source,
                        "fte",
                        str(row["fte"]),
                        "0 < FTE <= 1",
                        "Outside this demo's documented FTE policy; confirm the working schedule.",
                    )
                )
            try:
                hired = date.fromisoformat(row["hire_date"])
                ended = (
                    date.fromisoformat(row["termination_date"]) if row["termination_date"] else None
                )
                if ended and ended < hired:
                    raise ValueError("Termination precedes hire")
            except ValueError:
                findings.append(
                    Finding(
                        "DATE_SEQUENCE",
                        worker_id,
                        source,
                        "hire_date",
                        row["hire_date"],
                        "valid ISO dates; termination on/after hire",
                        "Check original employment dates.",
                    )
                )

    hr = indexed["workday"]
    for worker_id, row in hr.items():
        manager = row["manager_id"]
        if manager and (manager == worker_id or manager not in hr):
            findings.append(
                Finding(
                    "MANAGER_REFERENCE",
                    worker_id,
                    "workday",
                    "manager_id",
                    manager,
                    "another unique HR worker ID",
                    "Confirm reporting hierarchy with the HR owner.",
                )
            )
        try:
            current = date.fromisoformat(row["hire_date"]) <= as_of
        except ValueError:
            continue
        if not current or row["worker_type"] != "Employee" or row["status"] != "Active":
            continue
        for source in ("payroll", "core"):
            if source in stale or "workday" in stale:
                continue
            matching = indexed[source].get(worker_id)
            if matching is None:
                # Duplicate rows already have their own finding; don't call them missing.
                exists = any(r["worker_id"].strip() == worker_id for r in snapshots[source])
                if not exists:
                    findings.append(
                        Finding(
                            "MISSING_WORKER",
                            worker_id,
                            source,
                            "worker_id",
                            "",
                            worker_id,
                            "In-scope active employee missing. "
                            "Confirm onboarding and extract timing.",
                            "high",
                        )
                    )
                continue
            if row["cost_centre"] in COST_CENTRES and matching["cost_centre"] in COST_CENTRES:
                if row["cost_centre"] != matching["cost_centre"]:
                    findings.append(
                        Finding(
                            "COST_CENTRE_MISMATCH",
                            worker_id,
                            source,
                            "cost_centre",
                            matching["cost_centre"],
                            row["cost_centre"],
                            "Demo assumption: approved current HR cost centre is authoritative. "
                            "Confirm effective date and owner before correction.",
                        )
                    )
    return findings
