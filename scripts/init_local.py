"""Create local-only secrets once, without displaying their values."""

import secrets
from pathlib import Path

path = Path(".env")
if path.exists():
    raise SystemExit(".env already exists; preserved unchanged")
lines = ["APP_MODE=demo", "DB_PATH=data/local/people-quality.db", "API_URL=http://127.0.0.1:8000"]
lines += [f"{role}_KEY={secrets.token_urlsafe(32)}" for role in ("ANALYST", "REVIEWER", "OPERATOR")]
with path.open("x", encoding="utf-8") as output:
    output.write("\n".join(lines) + "\n")
print("Created .env with distinct random local demo keys. Values were not printed.")
