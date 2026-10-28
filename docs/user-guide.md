# Audit user guide

## Analyst

Start with the agreed snapshot date and population. Review the queue, then inspect the original
source records for the selected worker. Verify the field owner and reason for a discrepancy.
For E0035 in the supplied fixture, payroll has C200 while current synthetic HR has C100.
Record the evidence and request C100. A missing value is not permission to guess.

## Reviewer

Review the proposed value, previous value and reason. In this local demo, approve only when the
synthetic evidence supports it. Reject an unsupported request with a reason. Analysts can cancel a pending or approved request,
or escalate a case with evidence and a named team. Do not approve a guess.

## Operator

Apply the approved request. If the original value changed, investigate again rather than forcing
the update. A successful application reruns the audit, resolves its target case and records an event.
The CSV report includes open and resolved findings; filter by status to calculate open cases.

## FAQ

**Why is a worker missing from payroll?** Check scope, effective dates, employee type and onboarding.
A contractor or future hire may not belong in the current extract.

**Why not update every system immediately?** Ownership and update timing differ. An approved
change must follow the appropriate system's process and then be validated downstream.

**Does an active payroll record after termination prove an error?** No. Final pay may require it.
Confirm the payroll process and period before classifying it.

**Why did a duplicate fail?** A lookup could choose an arbitrary row or multiply joined records.
Resolve the duplicate with the source owner before cross-system comparison.


## Expanded workspaces

Use the sidebar Workspace selector. Bulk corrections supports preview, submission, review and
all-or-nothing application. Reports and trends provides source-date context and downloadable
synthetic source CSVs. Release testing exercises a deliberately faulty fictional release.
Guides and coaching retains guide versions and distinguishes self-practice from actual peer feedback.
Requirements workshop records a problem, acceptance criteria and review decision.
Practice setup creates independent exercise datasets without deleting previous runs.

Follow [the practice lessons](practice-lessons.md) in order. A new user should first explain one
employee mismatch confidently, then practise bulk changes and testing. An unresolved duplicate
or missing employee requires source-owner investigation, not a fabricated field value.
