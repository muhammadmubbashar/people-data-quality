# Step-by-step learning plan

## Step 1 — Understand the business question

Read README and data-contract.md. Explain why a payroll mismatch may be a timing difference.
Write a paragraph describing the risk of changing the wrong field in the wrong system.
Done when: you can distinguish a missing worker, duplicate key and valid payroll exclusion.

## Step 2 — Run a complete workflow

Start the API and UI using the scripts. Generate a demo run and investigate E0035.
Request C100, approve as reviewer and apply as operator. Read the event history and report.
Done when: you can explain why the app needs three identities and why this is still a simulation.

## Step 3 — Read the code by responsibility

Read demo.py, domain.py, store.py, then api.py and ui/app.py. Trace a field from fixture to finding
to correction. Run the tests and inspect how an unapproved or stale correction is rejected.
Done when: you can change a business rule and predict which tests should change.

## Step 4 — Make your first small engineering change

Create a branch, write acceptance criteria, add a failing regression test, implement the change,
run lint/format/tests and open a PR. Suggested task: add a valid cost-centre reference supplied
through configuration, rather than editing the constant in the domain module.
Done when: the PR contains a concrete problem, evidence and updated documentation.

## Step 5 — Work in a real HR platform

Follow workday-lab.md. Register yourself and request a personal development tenant.
Inspect the available worker data, reports, APIs, permissions and sample-data licensing before coding.
If unavailable, practise equivalent administration in your own Frappe HR trial instance.
Done when: you have evidence of actual platform tasks, clearly separate from simulated tasks.

## Step 6 — Reconcile a real platform's synthetic export in Excel

Define a minimal synthetic worker report. Preserve IDs as text. Practise filters, COUNTIFS,
exact XLOOKUP, missing-value checks, PivotTables and Power Query left/anti joins.
Check duplicates before lookup and confirm data types and dates before comparison.
Done when: you can explain one false alarm and one genuine defect with supporting records.

## Step 7 — Extend the project one requirement at a time

Follow roadmap.md: CSV ingestion, report mapping, actual read-only platform connection,
case rejection/escalation, bulk approval/execution, trends, user guides and release regression evidence.
Keep acceptance tests with each feature. Do not mark a real-platform feature done after only mock tests.

## Step 8 — Prepare your five-minute story

Explain the problem, show the source, investigate one finding, demonstrate approval/revalidation,
show a regression case and finish with what is implemented versus planned.
State which tasks ran in an actual Workday development tenant and which stayed in your local simulator.
