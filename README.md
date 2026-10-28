# People Data Quality and Payroll Readiness

[![Quality and integration](https://github.com/muhammadmubbashar/people-data-quality/actions/workflows/ci.yml/badge.svg)](https://github.com/muhammadmubbashar/people-data-quality/actions/workflows/ci.yml)

An independent HR systems portfolio project: investigate synthetic employee-data exceptions,
request a correction, obtain separate review, apply it to a simulated snapshot and revalidate.
Built to practise the work described in a People Systems Data Analyst vacancy.

**No affiliation with Flight Centre or Workday. No employer data. No Workday integration has
been verified yet.** The preferred next step is an authorised Workday personal development tenant.
The local app demonstrates the workflow while that access is being established.

## Start here

- [Your first lesson and demo](docs/step-by-step.md)
- [Architecture and diagram](docs/architecture.md)
- [Real Workday access and integration plan](docs/workday-lab.md)
- [Requirements and delivery milestones](docs/roadmap.md)
- [Production and scalability plan](docs/production.md)
- [User guide](docs/user-guide.md)

## What runs today

- FastAPI service with authenticated demo-role checks and documented REST endpoints.
- Streamlit interface for audit review, source comparison, correction requests, approvals and CSV reports.
- Pure audit rules: duplicate IDs, cost centres, FTE, manager references, dates and missing workers.
- Synthetic 100-worker example with seven expected exceptions and valid exclusion cases.
- Database-backed request/review/apply history; three distinct simulated identities.
- Cost-centre correction with approval, stale-value detection, transactional revalidation and repeat protection.
- Bulk dry-run endpoint. Batch execution is not implemented.
- Automated domain/API tests, dependency hash locks, lint and format checks, container configuration and CI.

## Windows setup

Use Python 3.12 or 3.13. In PowerShell from this folder:

```powershell
.\scripts\setup.ps1 -Python 'C:\path\to\python.exe'
```

If `.venv` already exists, setup uses it. It installs hash-locked development dependencies and
creates random local demo keys in ignored `.env`. It does not print credentials.
Start two terminals:

```powershell
.\scripts\run-api.ps1
```

```powershell
.\scripts\run-ui.ps1
```

Open [demo UI](http://127.0.0.1:8501), [API documentation](http://127.0.0.1:8000/docs)
or [health](http://127.0.0.1:8000/health). The API docs require a configured `X-API-Key`
for protected endpoints. The UI reads it server-side from your local `.env`.

## First five-minute demonstration

1. Select analyst and create a synthetic audit run: expect seven open findings.
2. Investigate E0035: current HR cost centre C100 differs from payroll C200.
3. Propose C100 with a reason explaining your synthetic source evidence.
4. Switch to reviewer, inspect the request and approve it.
5. Switch to operator, apply and revalidate: expect six remaining findings.
6. Review the three audit events and download the audit report.
7. Explain that individual identities, actual HR approvals and a real Workday correction are future integration work.

## Quality checks

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip_audit -r requirements.lock --disable-pip --no-deps
```

CI runs checks on Windows and Linux, audits the runtime dependency lock and builds/smoke-tests
both Docker services. CI does not deploy publicly. See the actual Actions run for remote status;
the existence of a workflow is not evidence that it passed.

## Containers

With Docker Engine and Compose available, first generate `.env`, then run `docker compose up --build`.
Both exposed ports bind to loopback. SQLite persists in a Docker volume. The image uses a
non-root user and the services drop Linux capabilities. Container behaviour must be verified in CI
or on a machine with Docker; see [production boundaries](docs/production.md).

## Repository structure

```text
src/people_quality/   pure rules, synthetic fixtures, API and SQLite repository
ui/                  Streamlit client
tests/               business-rule and API integration tests
scripts/             local setup and launch scripts
docs/                architecture, lessons, requirements and operational plans
.github/             CI, dependency updates and PR template
```

## Learning and limitations

This version deliberately uses a modular monolith. It has one service boundary and a small,
testable domain, avoiding distributed-system overhead before it has measured demand.
SQLite and the role-switching UI suit a local demonstration. They do not establish production
readiness, payroll compliance, Workday certification or professional HR experience.

Workday announced individual developer access in October 2026. Request your own development
tenant, inspect available capabilities, and then implement an evidence-backed integration.
The [Workday lab](docs/workday-lab.md) explains the next steps and fallback.
