# From Workday to an audit: your demonstration lesson

Think of this as taking a photocopy of employee facts, translating its column names, checking it,
then comparing it with two practice notebooks. We do not edit the original Workday notebook.

## 1. Collect the facts

The directory API originally supplied names and titles. Detailed Staffing records supplied employee
numbers, types and hire dates. WQL lets us select particular report columns, similar to a database
SELECT query. We discovered the actual column aliases from Workday metadata rather than guessing.

A cost centre is the business bucket receiving employee costs. FTE describes the proportion of a
full-time schedule: 1.0 is 100%, 0.5 is 50%. A manager is another worker with an employee number
and a separate internal ID. Employment flags describe active, terminated or leave status.

The Aidan sample returned employee 21142, cost centre 32100, FTE 1.0/100%, manager 21044 and hire
date 2020-01-01. These are Workday development sample values, not Flight Centre employee data.

## 2. Check the translation

Open Workspace > Workday sample data. Read Validated employment details and Field sources.
Employee numbers join the practice files. The long WID identifies the Workday object; it is not
interchangeable with an employee number. A supervisory organisation is not a cost centre.

The app checks employee/WID agreement, duplicates, FTE ratio versus percentage, hire dates across
APIs, explicit status flags and manager lookups. Missing data blocks import. It never guesses
that everyone works full time or belongs to a default cost centre.

## 3. Create a clean baseline

Click Create clean audit from Workday capture. Note the run ID. The app creates a read-only HR
snapshot and two labelled local copies containing the same facts. The expected baseline is zero
findings. This proves agreement on the supplied sample, not that every tenant record is correct.

## 4. Create a controlled problem

Click Create practice audit with two downstream errors. It changes a cost centre in the local
Payroll copy and an FTE value in the local Core copy. HR remains unchanged. Expect two findings.
The affected employees and old/new values are logged in provenance. These are training problems,
not observed Workday or employer defects.

## 5. Investigate and correct the copies

Open My work, select that run ID and read its source notice. Investigate the cost-centre mismatch.
Compare HR with Payroll, record evidence and request the captured HR value. Switch to reviewer,
approve, then operator and apply. One case should remain. Role switching simulates distinct people;
real independent approval requires individual identities.

For the FTE case open Bulk corrections as analyst, choose the same run and select the Core finding.
Use the actual HR FTE ratio in the source comparison. Preview, submit, review and apply. Expect
zero cases. A valid numeric range alone is insufficient: 0.75 cannot replace a captured 1.0 without
creating an FTE mismatch. Revalidation rejects that wrong proposal.

## 6. Explain the result

“I connected a personal Workday development tenant using OAuth and PKCE. Staffing and WQL supplied
employee, cost-centre, FTE, manager and employment information for a small sample. I verified IDs
and units before importing it. I used labelled practice payroll/Core copies to demonstrate
investigation, approval, correction and revalidation. The Workday source stayed read-only. Your
actual field ownership, security and integration timing would need confirmation with your team.”

Do not claim these are Flight Centre systems, that training errors came from Workday, or that
local approval performed a real Workday business process.

Before the interview, explain why 1.0 and 100 mean the same FTE, why a manager outside a five-row
sample is not automatically missing, and why zero findings is a scoped result rather than proof
of perfect data.
