# Verified Workday sample mapping — v0.3

Verified 29 October 2026: OAuth/PKCE authenticated to a personal development tenant. Staffing and WQL returned employee, cost-centre, FTE, manager and employment information for five sample workers. No Flight Centre systems are involved.

## Connection and scope

The account owner approved Staffing, then separately approved System for WQL. These functional scopes are broader than read-only roles. The connector uses GET for data/metadata and POST only for OAuth token exchange. Workday still enforces the account's data security. Tokens stay in memory, refresh tokens are discarded, and no employee records are written.

A seven-day local HTTPS certificate was trusted in CurrentUser after explicit approval. The callback binds to 127.0.0.1:8766, validates random state and PKCE, rejects repeat callbacks and suppresses access logs. Workday TLS verification remains enabled. Omitting the optional redirect_uri from authorization and token requests resolved HTTP 403 in this tenant, using its registered callback; this observation does not identify an internal gateway rule.

## Verified fields

- Staffing resolves workerId (employee number), internal WID, worker type and service-date hireDate.
- WQL allWorkers returns employeeID, worker, costCenter, costCenter_ID, FTE, FTEPct, managerID, manager_EffectiveDated, hireDate, activeStatus, terminated, onLeave, terminationDate and workerType.
- The case-sensitive aliases were discovered from tenant metadata. Each manager WID is separately resolved through Staffing and its employee number compared with managerID.
- FTE is a ratio and FTEPct a percentage. Values must agree: 1.0 equals 100%. Cost-centre code comes from costCenter_ID, never from parsing a display name.
- Employee numbers remain text, preserving leading zeroes. WIDs remain separate evidence.
- Missing fields, duplicate/unexpected IDs, unknown statuses, wrong joins, ambiguous managers and incompatible units quarantine the capture. Defaults such as C100, E0001 or 1.0 are never substituted.

The verified sample contains active employees. An omitted terminationDate is mapped to blank only with explicit terminated=false. Complex/inactive states and future termination events are blocked until their semantics are agreed. The query reads current tenant state, not a historical as-of report or a transactionally frozen cross-endpoint snapshot.

## Refresh and import

1. Store verified endpoints/public client ID in ignored data/local/workday-config.json.
2. Run scripts/connect_workday.py --discover to discover metadata and collect the sample.
3. Use --enrich for later reads using the observed local field metadata.
4. Open logs/workday-authorize-url.txt while the ten-minute listener runs and complete private sign-in/consent when required.
5. Open Workday sample data in the UI. All five staged rows must pass before import.
6. Choose a clean audit or a controlled training audit. Review source evidence and scoped policy before corrections.

GET /workday/capture shows the original minimal API capture. GET /workday/staging validates enriched records. Analyst-only POST /workday/audits creates a run. Every endpoint uses the existing demo-role authentication. The process saves evidence locally and exits; there is no continuous sync or write-back.

## Audit boundaries

HR is the Workday sample snapshot. Payroll and Core are explicitly labelled local copies. Training mode injects two logged errors only into those copies. Imported HR is read-only through single/bulk correction flows. Per-run policies preserve legacy C100/C200/C300 exercises. Native sample FTE values are reconciled against HR as well as range-checked, rejecting plausible but wrong corrections.

Cost-centre validation is limited to assignments resolved in this capture, not the full active finance master. Manager IDs were resolved through Staffing, but those managers are outside the five-row audit population. Full-population policy, payroll periods, effective-date history, production identity and actual downstream connectors remain future work.

Automated tests use fabricated responses; CI does not contact Workday. Actual tenant reads are separate manual integration checks. Tenant config, raw captures, certificates and keys are excluded from GitHub. A fresh checkout requires its own authorised tenant and capture.

Official sources:

- [REST fundamentals](https://developer.workday.com/documentation/GUID-85810465-bcfb-4fdf-a26d-55eaff3968a8-enHYPHENus)
- [Staffing API](https://developer.workday.com/rest-api-explorer/docs/staffing/v7)
- [WQL and System scope](https://developer.workday.com/documentation/GUID-6546152a-bcf0-447d-8d64-230f9e2ac291-enHYPHENus)
- [WQL metadata](https://developer.workday.com/documentation/GUID-5c940864-7651-4e28-a9d2-79b45292e66a-enHYPHENus)
