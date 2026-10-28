# Real platform lab

## Preferred: personal Workday development tenant

Current setup status (29 October 2026): the personal-account beta request was submitted and
the console confirmed **Access Request Pending**. No tenant has been provisioned or connected.
Workday will email the account owner after reviewing the request. The request described student
status and an independent synthetic-data HR learning project. Personal account details and
confirmation screenshots remain local and are not committed.

Workday's October 2026 announcement allows individuals to join the Developer Program with a
personal email and request a personal development tenant through its open-access beta.
This is more direct than assuming all Workday access must come through an employer.

1. Open https://developer.workday.com/ and register or sign in yourself.
2. Follow the current Console / Tenants flow to request a personal development tenant if offered.
3. Complete your own email verification and retain your credentials privately.
4. Check the available products, sample workers, security roles, report builder and integration APIs.
5. Record the tenant capabilities and limits in a local note; do not publish access URLs or credentials.
6. Run the official introductory learning. Start with read-only inspection and a minimal sample-data report.
7. Map authorised synthetic report fields to the local data contract and add adapter contract tests.
8. Only implement write-back after discovering actual supported business processes and permissions.

Personal access is a beta. Access, supported features and HR administrative permissions must
be verified on the provisioned tenant. Do not promise a full HCM or payroll training environment.
Official documentation says personal tenants expire after seven consecutive days without login;
verify the current policy and export permitted project evidence before expiry.

## Actual tasks to practise if permissions support them

- Inspect a sample worker, their organisation, manager and effective-dated history.
- Build a minimal worker report with prompts, filters and appropriate access.
- Compare its permitted synthetic export with a mock payroll extract locally.
- Investigate an issue and document the correct business-process action.
- Test one permitted change on sample data and check the resulting history/report.
- Record a short walkthrough with sensitive tenant details redacted.

Do not call a CSV export a native integration. Do not call a generic Developer/Extend exercise
Workday HCM administration if the tenant does not provide those capabilities.

## Fallback: Frappe HR

https://frappe.io/hr offers an official demo and free-trial route. It is a real open-source HR/payroll
platform. In your own authorised trial, practise employee records, approvals, reports and an API
integration with synthetic records. Pricing and trial duration must be confirmed at registration.

Its documented REST API uses DocTypes and role-scoped token authentication. Keep keys in local
environment configuration. Discover the actual installed schema before building an adapter.
Frappe HR experience is useful HRIS practice but is not Workday experience.

This Windows machine currently has neither Docker nor an installed WSL environment. We have
not installed those system components. A hosted personal trial avoids those local prerequisites.

## Sources checked 29 October 2026

- https://blog.workday.com/en-us/workday-open-developer-platform-generally-available.html
- https://developer.workday.com/documentation/GUID-4f875963-a845-43b5-868a-0f77e6261eb7-enHYPHENus/CreateandManagePersonalAccountDevelopmentTenants
- https://www.workday.com/en-us/services/training-certifications.html
- https://frappe.io/hr
- https://docs.frappe.io/framework/user/en/api/rest
