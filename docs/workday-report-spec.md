# Proposed Workday report specification

Status: a basic native report was created and run on 29 October 2026. See
[verified native practice](native-workday-practice.md). `PQ Practice - Active Worker Audit` uses
Workers for HCM Reporting / All Active Workers with Employee ID, Cost Center - ID, FTE, Manager ID,
Hire Date and Active Status. It returned 82 sample rows; a display filter showed worker 21038.
The broader specification below remains proposed: historical prompts, restricted-role validation,
full lifecycle coverage and web-service exposure have not been implemented or tested.

Purpose: obtain the minimum authorised synthetic worker data needed to investigate data quality.
Proposed primary object: Worker. Candidate data source: an available worker-reporting source
approved for the relevant population. Exact source names depend on tenant configuration.

Fields to map: worker identifier, employee/contingent type, active/leave/terminated status,
company, manager identifier, cost centre, work schedule/FTE and relevant effective dates.
Do not include names, payment details, tax identifiers or other personal fields for this project.

Prompts: as-of date, company/organisation and population. Define how future changes and leavers
are represented. Record report execution time and the actual effective-date semantics.

Security: only authorised lab users; test that a restricted role cannot retrieve unauthorised rows
or fields. Exporting data must preserve the same scope. Native report creation is not implemented
by the local API's CSV endpoint.

Validation: key uniqueness, known mappings, totals against the permitted worker population,
sample checks, reproducible date filters and a clear owner/review date. Retain only permitted
synthetic evidence. Add contract tests once a real sample-data report is available.
