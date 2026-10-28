# Project instructions

- Synthetic data only. Never add employer files, credentials or claims of affiliation.
- Explain user-visible changes in plain language and update the relevant lesson or runbook.
- Keep audit rules pure in domain.py and persistence in store.py.
- Preserve separation between requester, reviewer and operator in API authorisation.
- Never weaken tests or safety checks to make CI pass.
- Run ruff check, ruff format --check and pytest before committing code changes.
- Distinguish implemented features, tested behaviour and future production design.
- Actual Workday access, employee data, infrastructure provisioning and public deployment are
  outside this local demo's scope unless explicitly authorised in a later request.
