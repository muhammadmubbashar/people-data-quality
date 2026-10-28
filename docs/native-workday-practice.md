# Native Workday practice: People Systems Data Analyst

Verified in the account owner's personal development tenant on 29 October 2026.
These are fictional enterprise sample records, not Flight Centre records.

## Completed native work

- Searched employee 21038 and inspected Angela Bianchi's profile.
- Confirmed manager Jake Lee, FTE 100%, hire date 1 January 2015.
- Opened Job > Organizations and inspected cost centre 71100 Sales East - NA.
- Created and saved `PQ Practice - Active Worker Audit`, a Simple custom report.
- Source: Workers for HCM Reporting. Source filter: All Active Workers.
- Columns: Employee ID, Cost Center - ID, FTE, Manager ID, Hire Date, Active Status.
- Ran the report: 82 active sample rows were returned at this execution.
- Applied an Employee ID display-column filter containing `21038`: one row remained,
  showing 71100, FTE 1, manager 21053, hire date 01/01/2015 and Active Status Yes.
- Found native Change Organization Assignments and Launch Mass Change Organization Assignments
  for Worker tasks. Inspected the former's initial effective-date/supervisory-organisation prompt
  and cancelled without submitting a worker change. Finding a task is not executing an approval.

The display filter is not a security boundary or a saved five-worker source restriction.
The report is current active-worker reporting, not a historical/leaver audit. Its role visibility
has not been tested with a restricted user. No report sharing or web-service exposure was added.
No broad export was downloaded or imported into the local five-worker exercise.

## Explain the three places

Workday HCM holds worker facts and native HR business processes. The Developer Console configures
developer resources and shows application logs; it is not the worker reporting screen. The local
audit app compares a saved five-worker Workday capture against simulated Payroll and Core records.
Its role switches and approvals are local simulations, not Workday Inbox approvals.

## Repeat the native reporting exercise

1. Sign into the development tenant privately.
2. Search `21038`, open Angela Bianchi, and verify Employee ID before comparing any facts.
3. Read Summary/Job Details for FTE, hire date and manager. Open Job > Organizations for cost centre.
4. Search `PQ Practice - Active Worker Audit` and run it. Optional worker-type prompts narrow population.
5. On the Employee ID column, select the filter, enter `21038` and apply it.
6. Compare the report row with the profile and saved API capture. FTE 1 equals 100%, not 1%.
7. State the report's population and execution timing. Do not treat active-only results as all workers.

## How the advert maps to actual work

For audit-tool support and coaching, explain flagged records, dates, owners and next steps in the
existing tool, and write a short user guide. Workday does not replace coaching or a support queue.

For investigation, inspect the worker profile, organisation assignments, reports and available
event history. Confirm approved facts and effective dates with HR/payroll owners. A mismatch
does not establish its root cause, and majority agreement does not establish ownership.

For corrections, use the approved native business process for the relevant field and event.
Changing a future assignment is different from correcting an erroneous historical event. Confirm
the tenant's routing, permissions and downstream impact before submission. An administrator
practice login does not prove an independent requester/reviewer approval route.

For bulk corrections, a senior owner selects the supported process or inbound integration,
prepares a field-specific template, validates a small sample, reviews exceptions and approves the
load. Workday EIB supports inbound/outbound integration patterns, but no inbound load or native
bulk correction has been executed here.

For cross-system alignment, compare Workday with authorised Payroll/Core extracts using verified
employee keys, compatible effective dates and an agreed owner for each field. The employer's Core
product and integration schedules are unknown. Our downstream copies remain explicitly simulated.

For recurring trends, group repeated exceptions by rule, source, period and agreed root cause.
For release testing, capture expected results, run agreed scenarios in a test tenant, record actual
results and log reproducible defects. A personal developer tenant cannot prove an employer's
release compatibility, production security or payroll processing.

For relationships and requirements, ask HR, payroll and systems owners who approves each field,
when integrations run, which discrepancies are expected, and how completion is evidenced.

## Boundaries

Employee 21038's Workday cost centre was already correct. The local Payroll discrepancy was
deliberately injected. Correcting Workday would therefore be the wrong action for that case.
Native worker changes, independent approvals, inbound bulk loads, employer integrations and
release testing must not be claimed as completed on the strength of the report exercise.

Official references:
- https://www.workday.com/content/dam/web/en-us/documents/datasheets/datasheet-workday-human-capital-management.pdf
- https://doc.workday.com/workday-education/en-us/course-manuals/security-for-administrators/integrations.html
