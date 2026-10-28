"""Read-only tenant probe using short-lived, in-memory OAuth credentials.

This does not map incomplete API responses into the audit model or write to Workday.
"""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode, urlsplit

import requests


class ConnectionError(Exception):
    """Sanitised diagnostic; never include a token or remote response body."""


def token_failure(response):
    """Classify failures without exposing tokens, codes or arbitrary response text."""
    diagnostic = f"Workday token request returned HTTP {response.status_code}"
    if "text/html" in response.headers.get("Content-Type", "").lower():
        if "request has been blocked" in response.text.lower():
            return diagnostic + " (Workday gateway block, before OAuth processing)"
        return diagnostic + " (HTML response; not a normal OAuth error)"
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return diagnostic
    if error in {
        "invalid_client",
        "invalid_grant",
        "invalid_request",
        "unauthorized_client",
        "unsupported_grant_type",
        "invalid_scope",
        "access_denied",
    }:
        return diagnostic + f" (OAuth {error})"
    return diagnostic


@dataclass(frozen=True)
class Tenant:
    authorization_url: str
    token_url: str
    workers_url: str
    client_id: str
    redirect_uri: str = "https://127.0.0.1:8766/callback"

    def __post_init__(self):
        for url in (self.authorization_url, self.token_url, self.workers_url):
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or not parsed.hostname.endswith(".myworkday.com")
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.port not in (None, 443)
            ):
                raise ValueError("Use verified HTTPS Workday tenant endpoints")
        if self.redirect_uri != "https://127.0.0.1:8766/callback":
            raise ValueError("Only the fixed loopback callback is supported")
        if not self.client_id or len(self.client_id) > 256:
            raise ValueError("Supply the registered public client ID")


class Handshake:
    def __init__(self, tenant):
        self.tenant = tenant
        self.state = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(64)
        self.used = False

    def authorization_url(self):
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        return (
            self.tenant.authorization_url
            + "?"
            + urlencode(
                {
                    "response_type": "code",
                    "client_id": self.tenant.client_id,
                    # Workday permits omission and uses the registered redirect.
                    # An explicit loopback redirect triggered its gateway in this tenant.
                    "state": self.state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    def exchange(self, code, state, session):
        if self.used or not secrets.compare_digest(state, self.state) or not code:
            raise ConnectionError("Invalid, missing or already consumed OAuth callback")
        self.used = True
        try:
            response = session.post(
                self.tenant.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.tenant.client_id,
                    # The authorization request omitted redirect_uri, so the token
                    # request also uses the client's registered callback implicitly.
                    "code": code,
                    "code_verifier": self.verifier,
                },
                timeout=(5, 25),
                allow_redirects=False,
            )
        except requests.RequestException:
            raise ConnectionError("Workday token request could not complete") from None
        if response.status_code != 200:
            raise ConnectionError(token_failure(response))
        try:
            body = response.json()
            token = body["access_token"]
            if not isinstance(token, str) or not token:
                raise ValueError
            if body.get("token_type", "Bearer").lower() != "bearer":
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ConnectionError("Workday token response has an unsupported format") from None
        return token  # Refresh token deliberately discarded; nothing is persisted.


def read_workers(tenant, token, session, limit=5):
    if not 1 <= limit <= 20:
        raise ValueError("The initial probe allows 1–20 sample workers")
    try:
        with session.get(
            tenant.workers_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"limit": limit, "offset": 0},
            timeout=(5, 25),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise ConnectionError(f"Workday worker read returned HTTP {response.status_code}")
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 1_000_000:
                    raise ConnectionError("Workday response exceeds the probe size limit")
            result = json.loads(content)
    except requests.RequestException:
        raise ConnectionError("Workday worker read could not complete") from None
    except (ValueError, UnicodeError):
        raise ConnectionError("Workday worker response is not valid JSON") from None
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise ConnectionError("Worker response requires a data array; inspect its actual contract")
    if len(result["data"]) > limit:
        raise ConnectionError("Workday returned more rows than requested")
    return result


def capture_summary(path):
    """Expose a minimal saved sample preview, never tokens, emails or tenant URLs."""
    if not path.exists():
        return {"status": "not_captured", "live_session": False, "workers": []}
    if path.stat().st_size > 2_000_000:
        raise ConnectionError("Saved Workday capture exceeds the preview size limit")
    try:
        raw = path.read_bytes()
        saved = json.loads(raw)
        if (
            saved["source"] != "personal_workday_development_tenant"
            or saved["mode"] != "read_only_api_probe"
            or saved["sample_only"] is not True
            or saved["audit_imported"] is not False
        ):
            raise ValueError
        rows = saved["response"]["data"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
            raise ValueError
        if saved["received_rows"] != len(rows):
            raise ValueError
        workers = [
            {
                "workday_id": r["id"],
                "sample_worker": r.get("descriptor", ""),
                "job_title": r.get("businessTitle", ""),
                "supervisory_organisation": (r.get("primarySupervisoryOrganization") or {}).get(
                    "descriptor", ""
                ),
            }
            for r in rows
        ]
        checked_at = saved["checked_at"]
        if datetime.fromisoformat(checked_at).tzinfo is None:
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ConnectionError("Saved Workday capture has an unsupported format") from None
    return {
        "status": "verified_api_capture",
        "live_session": False,
        "checked_at": checked_at,
        "received_rows": len(workers),
        "workers": workers,
        "capture_sha256": hashlib.sha256(raw).hexdigest(),
        "audit_imported": False,
        "not_provided_by_this_endpoint": [
            "cost_centre",
            "fte",
            "manager_id",
            "worker_type",
            "status",
            "hire_date",
        ],
        "note": "Last saved API response, not a persistent connection. "
        "The access token was discarded. Local evidence is not tamper-proof.",
    }
