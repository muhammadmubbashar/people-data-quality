# Audit user guide

## Analyst

Start with the agreed snapshot date and population. Review the queue, then inspect the original
source records for the selected worker. Verify the field owner and reason for a discrepancy.
For E0035 in the supplied fixture, payroll has C200 while current synthetic HR has C100.
Record the evidence and request C100. A missing value is not permission to guess.

## Reviewer

Review the proposed value, previous value and reason. In this local demo, approve only when the
synthetic evidence supports it. Rejection/escalation is not implemented yet: do not approve a
request that you cannot support. Leave it pending and record the limitation in your walkthrough.

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
