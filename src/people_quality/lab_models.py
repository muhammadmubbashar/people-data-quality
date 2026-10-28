"""Explicit contracts for practice workflows, not vendor API schemas."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Team = Literal["HR", "Payroll", "GPS", "Workday support", "Finance"]
RootCause = Literal[
    "Unknown", "Data entry", "Integration timing", "Mapping", "Missing approval", "Training"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseUpdate(StrictModel):
    owner: Team
    priority: Literal["low", "medium", "high"]
    state: Literal["investigating", "waiting", "escalated", "closed_no_change"]
    root_cause: RootCause
    evidence: str = Field(min_length=10, max_length=3000)
    next_action: str = Field(min_length=5, max_length=1000)
    due_date: date
    expected_version: int = Field(default=0, ge=0)


class Reason(StrictModel):
    reason: str = Field(min_length=10, max_length=1000)


class BatchItem(StrictModel):
    finding_id: str
    new_value: str = Field(min_length=1, max_length=50)


class BatchCreate(Reason):
    items: list[BatchItem] = Field(min_length=1, max_length=100)


class Article(StrictModel):
    title: str = Field(min_length=5, max_length=150)
    audience: Team
    body: str = Field(min_length=20, max_length=8000)
    review_date: date
    expected_version: int = Field(default=0, ge=0)


class Coaching(StrictModel):
    evidence_kind: Literal["self_practice", "peer_feedback"]
    learner_alias: str = Field(min_length=2, max_length=40)
    question: Literal["timing", "approval", "export"]
    answer: str = Field(min_length=10, max_length=2000)
    feedback: str = Field(min_length=10, max_length=2000)


class Requirement(StrictModel):
    title: str = Field(min_length=5, max_length=150)
    team: Team
    business_problem: str = Field(min_length=10, max_length=2000)
    acceptance_criteria: str = Field(min_length=10, max_length=3000)
    decision: str = Field(min_length=10, max_length=2000)
    evidence_kind: Literal["self_practice", "peer_workshop"]
    expected_version: int = Field(default=0, ge=0)


class RequirementDecision(Reason):
    expected_version: int = Field(ge=1)


class TestRequest(StrictModel):
    release: Literal["stable", "candidate_bug", "candidate_fixed"]


class DefectCreate(StrictModel):
    test_run_id: str
    case_name: str
    impact: str = Field(min_length=10, max_length=1000)
    steps: str = Field(min_length=10, max_length=2000)


class DefectResolution(Reason):
    passing_test_run_id: str
    expected_version: int = Field(ge=1)
