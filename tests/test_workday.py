import json
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from people_quality.workday import ConnectionError, Handshake, Tenant, read_workers, token_failure


def tenant():
    return Tenant(
        "https://example.myworkday.com/demo/authorize",
        "https://example.myworkday.com/ccx/oauth2/demo/token",
        "https://example.myworkday.com/ccx/api/v1/demo/workers",
        "public-client-id",
    )


def test_pkce_state_and_single_use():
    flow = Handshake(tenant())
    query = parse_qs(urlsplit(flow.authorization_url()).query)
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) == 43
    assert "redirect_uri" not in query
    session = Mock()
    with pytest.raises(ConnectionError, match="Invalid"):
        flow.exchange("code", "wrong-state", session)
    session.post.assert_not_called()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = {"access_token": "private-test-token"}
    assert flow.exchange("code", flow.state, session) == "private-test-token"
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert session.post.call_args.kwargs["data"]["code_verifier"] == flow.verifier
    assert "redirect_uri" not in session.post.call_args.kwargs["data"]
    with pytest.raises(ConnectionError, match="consumed"):
        flow.exchange("code", flow.state, session)


@pytest.mark.parametrize(
    "body", [{}, {"access_token": ""}, {"access_token": "x", "token_type": "MAC"}]
)
def test_bad_token_response_is_sanitised(body):
    flow, session = Handshake(tenant()), Mock()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = body
    with pytest.raises(ConnectionError, match="unsupported"):
        flow.exchange("code", flow.state, session)


def test_read_probe_only_gets_bounded_workers():
    session = MagicMock()
    response = session.get.return_value.__enter__.return_value = Mock()
    response.status_code = 200
    response.iter_content.return_value = [json.dumps({"data": [{"id": "sample"}]}).encode()]
    assert len(read_workers(tenant(), "private-test-token", session)["data"]) == 1
    session.post.assert_not_called()
    assert session.get.call_args.kwargs["params"] == {"limit": 5, "offset": 0}
    response.iter_content.return_value = [b"x" * 1_000_001]
    with pytest.raises(ConnectionError, match="size limit"):
        read_workers(tenant(), "private-test-token", session)


@pytest.mark.parametrize("url", ["http://example.myworkday.com", "https://myworkday.com.evil.test"])
def test_untrusted_endpoint_rejected(url):
    with pytest.raises(ValueError, match="verified HTTPS"):
        Tenant(url, tenant().token_url, tenant().workers_url, "client")


def test_token_failure_does_not_disclose_remote_details():
    response = Mock(status_code=403, headers={"Content-Type": "text/html"})
    response.text = "Your request has been blocked. sensitive-debug-detail"
    assert "gateway block" in token_failure(response)
    assert "sensitive" not in token_failure(response)
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {"error": "invalid_grant", "error_description": "private-code"}
    assert "OAuth invalid_grant" in token_failure(response)
    assert "private-code" not in token_failure(response)


def sample_capture():
    return {
        "source": "personal_workday_development_tenant",
        "mode": "read_only_api_probe",
        "sample_only": True,
        "audit_imported": False,
        "received_rows": 1,
        "checked_at": "2026-10-29T01:00:00+00:00",
        "response": {
            "data": [
                {
                    "id": "sample-id",
                    "descriptor": "Synthetic Example",
                    "businessTitle": "Analyst",
                    "primaryWorkEmail": "exclude-this@example.test",
                    "href": "https://private-tenant.example.test/worker",
                    "primarySupervisoryOrganization": {"descriptor": "Sample Reporting Group"},
                }
            ]
        },
    }


def test_capture_api_is_authenticated_and_minimises_fields(tmp_path):
    from fastapi.testclient import TestClient

    from people_quality.api import Settings, create_app

    keys = {
        role: role + "-capture-test-" + "x" * 32 for role in ("analyst", "reviewer", "operator")
    }
    with TestClient(create_app(Settings(str(tmp_path / "capture.db"), keys))) as api:
        assert api.get("/workday/capture").status_code == 401
        headers = {"X-API-Key": keys["analyst"]}
        assert api.get("/workday/capture", headers=headers).json()["status"] == "not_captured"
        path = tmp_path / "workday-probe.json"
        path.write_text(json.dumps(sample_capture()), encoding="utf-8")
        response = api.get("/workday/capture", headers=headers)
        assert response.status_code == 200
        assert response.json()["received_rows"] == 1
        assert response.json()["live_session"] is False
        assert "exclude-this" not in response.text
        assert "private-tenant" not in response.text
        assert "cost_centre" not in response.json()["workers"][0]
        path.write_text("{}", encoding="utf-8")
        assert api.get("/workday/capture", headers=headers).status_code == 422


@pytest.mark.parametrize(
    "change", [{"sample_only": False}, {"received_rows": 2}, {"checked_at": "bad"}]
)
def test_capture_rejects_invalid_provenance(tmp_path, change):
    from people_quality.workday import capture_summary

    path = tmp_path / "capture.json"
    path.write_text(json.dumps({**sample_capture(), **change}), encoding="utf-8")
    with pytest.raises(ConnectionError, match="unsupported"):
        capture_summary(path)
