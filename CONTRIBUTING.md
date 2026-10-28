# Working agreement

Use one branch and PR per business improvement. Define the problem, owner, acceptance criteria,
edge cases and evidence before implementation. Keep domain rules separate from UI and persistence.

Run all quality checks listed in README. Update documentation when data contracts or behaviour
change. Review dependency changes and regenerate both hash locks using a pinned version of uv.
Current generation command used uv 0.13.6:

```powershell
uv pip compile pyproject.toml --python-version 3.12 --universal --generate-hashes -o requirements.lock
uv pip compile pyproject.toml --extra dev --python-version 3.12 --universal --generate-hashes -o requirements-dev.lock
```

CI must pass before merging. Repository branch protection is not configured automatically by
this document; enable required checks where the account plan supports it. Never commit .env,
tenant credentials, employer extracts or personal account screenshots.
