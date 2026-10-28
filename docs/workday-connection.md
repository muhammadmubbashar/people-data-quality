# Personal Workday connection: staged setup

The account owner completed first login to a personal development tenant. Native HR Operations,
API client reporting and tenant-specific REST/token/authorization endpoints were inspected.
No Flight Centre tenant or records are involved. Tenant details stay in ignored local configuration.

## Verified read-only connection — 29 October 2026

The one-shot probe uses OAuth Authorization Code with PKCE and state verification. The native
registration form rejects plain HTTP redirects, so the callback uses HTTPS on 127.0.0.1:8766.
The application makes a bounded GET of at most five sample workers after token exchange.
Tokens are held in memory, refresh tokens are discarded and HTTP redirects are not followed.
It cannot update Workday records. The local response remains under data/local, outside Git.

The account owner approved client creation and local certificate trust. The registered client is
People Quality Local Practice, with the Staffing functional scope, PKCE, Bearer tokens and the
fixed HTTPS callback. Administrative consent, all-system-user access and non-expiring refresh
tokens remain off. A functional scope is not a read-only security role: the app's GET-only code
limits its behaviour, while actual Workday permissions follow the authenticating user's security.
Future least-privilege service-account setup is a separate task.

To enable HTTPS without bypassing browser warnings, a seven-day development certificate with
localhost and 127.0.0.1 SANs was prepared and trusted in the current user's store after explicit
confirmation. No Workday TLS checks are disabled. Remove that exact certificate after the exercise or when it expires.
Its private key is ignored by Git; do not share the data/local directory.

The first authorization request was blocked by Workday's gateway when it included the optional
redirect_uri parameter. Omitting that documented optional parameter reached the normal Workday
sign-in page, using the fixed URI already registered on the client. No protection was disabled.
The token request initially also contained the optional redirect_uri field and returned HTTP 403.
Omitting it from both requests succeeded using the registered callback: OAuth authenticated and
GET /workers returned five sample rows. This is an observed resolution, not proof of the gateway's
internal rule. Requests keep certificate verification enabled.

The returned fields were id, descriptor, href, primaryWorkEmail, primarySupervisoryOrganization,
isManager and businessTitle. The UI only exposes sample ID/name/title/supervisory group, not emails
or tenant URLs. A supervisory organisation is not a cost centre. Cost centre, FTE, manager ID,
worker type, status and hire date were not supplied by this response. No audit-model import occurred.
The local API capture is evidence of one successful read, not a persistent authenticated session.

## Connection sequence

1. Prepare the local HTTPS certificate with scripts/prepare_workday_tls.ps1.
2. Review and confirm the API client and local certificate trust actions.
3. Register the client and record only its public ID and verified endpoints in
   data/local/workday-config.json (matching the Tenant model).
4. Start scripts/connect_workday.py. It listens on loopback for ten minutes, with access logging off.
5. Open its locally saved authorization URL and review Workday's consent screen before authorizing.
6. Inspect the probe result and actual field contract; do not invent missing HR fields.
7. Implement and test field mapping before importing records into the three-source audit model.

The verified worker-list response did not include cost centre, FTE, manager or effective dates.
A successful GET proves authentication and a worker read, not full HR reconciliation coverage.
Do not fill missing fields using the old fictional C100/E0001 defaults.

Sources: Workday's official Create Your API Client, PKCE Authentication and WCP Development Tenants
documentation, plus the signed-in tenant's native registration form and API client report.


## See it in the demo

Open Workspace > Workday sample data. It shows the last captured sample and the Brisbane capture
time. The one-shot OAuth process exits after the read and discards the access token. No refresh
token is stored. To fetch a new capture, repeat steps 4–6; an existing Workday login may avoid
another password prompt. Local configuration and captures are intentionally absent from GitHub,
so a fresh checkout shows “No verified capture” until its owner connects their own tenant.

Automated tests use fabricated responses and no network credentials. They verify state/PKCE,
one-use callbacks, request boundaries, safe error messages and authenticated/minimised preview.
The actual five-row API read was a separate local manual integration check.
