# Security and data handling

This independent project accepts synthetic demonstration data only. It has no affiliation with
Flight Centre and does not access Workday, payroll providers or employer systems.

Run on loopback only. The UI deliberately lets one local demonstrator switch between three
role identities. API keys are randomly generated in ignored `.env`; they demonstrate server-side
authorisation but do not establish real employee identity or enterprise segregation of duties.

Do not expose this demo to the internet or upload employee records. Real deployment requires
SSO, individual identities, access scoping, privacy review, retention controls, encrypted storage,
backup and restore exercises, rate limits and an approved incident response process.

CSV exports neutralise spreadsheet formula prefixes. SQL values use parameters. Corrections
require reviewer approval and stale-value checks inside transactions. Application audit events
are database records, not tamper-proof compliance evidence: a database administrator can alter them.

Report a vulnerability using a private GitHub security advisory where available. Do not attach
credentials or employee information to issues.
