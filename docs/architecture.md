# Architecture

## Current local design

```mermaid
flowchart LR
    U[Local demonstrator] --> UI[Streamlit UI]
    UI -->|Role-specific demo API key| API[FastAPI service]
    J[Synthetic JSON snapshots] --> API
    API --> RULES[Pure validation and reconciliation rules]
    API --> STORE[SQLite repository and transactions]
    STORE --> RUNS[Run snapshots and findings]
    STORE --> CHANGES[Requests, approvals and events]
    STORE --> CASES[Case ownership and investigation evidence]
    STORE --> BATCHES[Atomic batch proposals and approval history]
    STORE --> DOCS[Versioned guides, requirements and coaching]
    STORE --> TESTS[Release results and defects]
    API --> CSV[Filtered reports and three-source CSV download]
    API --> REGRESSION[Executable fictional release scenarios]
    RULES --> API
    API -. planned authorised export or API .-> WD[Personal Workday development tenant]
```

Solid edges are implemented. The dashed integration is planned, pending access and capability checks.
This is an integration to a personal development tenant, never Flight Centre's production tenant.

## Data flow

The API validates JSON structure through Pydantic, then invokes a pure audit function.
Rules normalise IDs for matching, quarantine duplicate keys and compare only the documented
current-employee population. The SQLite repository persists each run, findings and workflow history.
The UI never accesses the database directly.

For corrections, an analyst requests a cost-centre change. A reviewer approves it. An operator
applies it inside a write transaction only if the source still matches the reviewed value.
The service reruns the rules before committing; unresolved target findings or new exceptions
roll back the entire operation. A second application returns the existing applied status.

## Decisions

- **Modular monolith:** fast local feedback and clear business rules; split jobs only when measured load warrants it.
- **FastAPI:** request validation and an inspectable API contract.
- **Streamlit:** quick analyst-facing demonstration; not intended as an enterprise identity boundary.
- **SQLite:** portable local state. Single-writer contention and unpaginated responses constrain scale.
- **Pure rules:** validate edge cases without web/database dependencies.
- **Explicit ownership:** a mock HR-authoritative cost-centre policy, not majority voting between systems.
- **Approval before mutation:** no automated direct write-back to a real HR platform.

## Trust boundaries

The local role selector has access to all three demo keys. It proves server-side role enforcement,
not independent human approval. Audit events are ordinary database rows, not immutable records.
All users can read all synthetic runs. Production needs individual SSO identities, scoped access
and independently protected audit storage before handling employee data.

## Expanded workflow and storage

A run stores both the original capture and a working copy. Corrections change the working copy;
original captures remain available for explaining what was first observed. Legacy runs are labelled
migration_current_state because their true original source rows cannot be reconstructed.
Source dates are compared before cross-system reconciliation: mismatched captures create a timing
finding and prevent corrections until a new aligned capture is supplied.

The case workspace records a responsible team, priority, evidence, uncertainty, next action and
follow-up date. An optimistic version check prevents overwriting another saved investigation.
Batches apply all reviewed rows in one database transaction, or save none of them. A stale row
invalidates the proposal. Rejection and cancellation preserve the decision history.

Documents retain successive versions. A simulated requirement needs reviewer acceptance. A defect
is linked to a failed executable scenario; resolution requires matching passing retest evidence.
These are local teaching controls, not Workday business processes or production audit guarantees.

Schema version 2 adds run_context, case_work, batches, lab_events, documents and test_runs.
The startup migration preserves old runs and changes. Back up the database before upgrading.
