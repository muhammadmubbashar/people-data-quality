# Your practice route: understand, do, explain

This is a fictional HR operations lab. Think of three notebooks about the same employees:
HR records the employment facts, Payroll uses relevant facts to pay people, and a third fictional
system called Core needs matching information. Flight Centre's actual Core and integration design
are not known. The auditing tool is the helper that points to disagreements; you investigate them.

You are practising an analyst's decisions. Building this lab does not imply the vacancy requires
you to build a new HR platform. The advert describes supporting their existing tools and users.

## 1. Investigate before changing anything

Open Practice setup as analyst and create a fresh seven-finding dataset. Open My work and select
E0035. Payroll says C200; the fictional HR record says C100. A cost centre is the business bucket
that receives the employee's costs. A disagreement can affect reporting even when pay is correct.

Open investigation notes. Assign Payroll, record the conflicting values and the source evidence,
leave root cause Unknown until established, and name the next action and follow-up date.
Try waiting or escalated if the source owner needs to confirm a pending transfer. A difference
alone does not prove which system is wrong. Do not close the case just because you wrote a note.

Explain: “I checked the dates and employee scope, compared the records, documented the evidence,
and asked the responsible team to confirm the authorised value.”

## 2. Correct several records safely

Use a new fresh run. In Bulk corrections select E0003 cost centre, E0012 FTE, E0015 manager,
E0035 payroll cost centre and E0045 Core cost centre. Use C100, 1.0, E0001, C100 and C100
respectively. These are practice answers to the fixture, not facts to assume in a real company.
Document a reason that explains the fictional evidence for each change.

Preview should show seven findings becoming two; nothing has been written yet. Submit for review.
Switch to reviewer, inspect the old/new values and reason, then approve. Switch to operator and
apply. The whole batch succeeds together or saves nothing. The duplicate and missing employee
remain because replacing one field is not a justified solution to those problems.

Explain: “A preview is a rehearsal. Approval gives permission. Application saves the permitted
changes. Validation checks the result and checks that we did not create a new problem.”

## 3. Spot a timing problem

Create the mismatched-date exercise. Payroll represents yesterday while the other sources represent
today. Investigate SNAPSHOT_DATE. The tool suppresses unsafe comparisons and blocks corrections.
Your next step is to request an aligned extract or confirm the agreed timing policy with the owner.
Do not change a value to hide an expected overnight difference.

## 4. Report a pattern, then investigate its cause

Create three dated captures. Open Reports and trends; history-practice shows initial case counts
seven, six and five across three dates. These are deliberately constructed, independent captures.
Filter a report and distinguish cases from distinct affected employees. Several cases can belong
to one person. Unknown root cause means it has not been established, not that the tool failed.

Explain: “If a mapping error repeats, fixing records helps today; asking the integration owner to
fix the mapping can prevent tomorrow's cases. I would first confirm evidence with that owner.”

## 5. Catch a faulty release

In Release testing run candidate_bug. The paid-leave scenario should fail because the fictional
change wrongly treats a worker on leave as a payroll defect. Record who is affected, the steps to
reproduce it, expected behaviour and the observed failure. Run candidate_fixed. As reviewer,
select its passing evidence and resolve the defect. Regression means checking an old working
behaviour still works after a change. These are this app's releases, not actual Workday releases.

## 6. Teach and improve a guide

In Guides and coaching read the payroll FAQ. Explain the timing issue out loud without jargon.
Record self_practice, your explanation and what needs improvement. If a real willing peer takes
part, you can record peer_feedback truthfully. Edit the guide; old versions remain available.
Ask your learner to explain the next step back to you: that checks understanding.

## 7. Agree a requirement

In Requirements workshop describe: “Payroll users need to distinguish old extracts from actual
data errors.” Write: “Given payroll is dated yesterday, when today's audit runs, then show a timing
warning and prevent automatic correction.” Record assumptions and open questions. Submit, then
review as reviewer. Use self_practice unless a real participant actually joined your workshop.

## 8. Practise Excel on the same evidence

Download captured source files from Reports and trends. Unzip and import each CSV through Excel
Data > From Text/CSV, keeping worker_id as text. Preserve the manifest and raw files.
Filter blank cost centres; use COUNTIF to detect duplicate IDs before any lookup. Compare unique
IDs across sources with XLOOKUP, check differences with IF, and summarise exceptions in a PivotTable.
Confirm E0035's captured mismatch. Download current files after correction and compare again.
Editing the downloaded files does not update the app or any HR system.

## 9. Plan a real Workday report

In a permitted tenant, first agree purpose, date, population and access with your supervisor.
Ask which approved data source and security domain to use. Specify worker ID, employee type,
status, cost centre, manager, FTE and relevant effective dates. Add agreed prompts and filters;
validate known examples and totals with the owner before sharing. Actual field names, available
report types and permissions depend on the tenant. Do not invent API endpoints or access.

The real job may use an existing report/export and auditing tool. You may run it, explain findings,
coordinate a permitted Workday business process and validate downstream results. Integration teams
may own APIs and scheduled transfers. You do not need to assume you will write those integrations.

## Your short interview explanation

“I built a synthetic practice lab around your advertised workflow. It compares employee records,
helps investigate exceptions, records ownership and evidence, and requires review before changes.
It also demonstrates bulk validation, reporting, regression testing and user guides. I can show
the decision process, while recognising your actual Workday permissions and processes must be
learned from your team. I have not connected this lab to Flight Centre systems.”
