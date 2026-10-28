import json
from unittest.mock import MagicMock

import pytest

from people_quality.workday import ConnectionError, Tenant
from people_quality.workday_enrichment import discover, read_json


def tenant():
    return Tenant(
        "https://example.myworkday.com/demo/authorize",
        "https://example.myworkday.com/ccx/oauth2/demo/token",
        "https://example.myworkday.com/ccx/api/v1/demo/workers",
        "test-client",
    )


def transport(body=None, status=200):
    session = MagicMock()
    response = session.get.return_value.__enter__.return_value
    response.status_code = status
    response.iter_content.return_value = [json.dumps(body or {"data": []}).encode()]
    return session


def test_discovery_is_read_only_and_reports_real_permission_failures():
    session = transport(status=403)
    result = discover(tenant(), {"data": [{"id": "a" * 32}]}, "test-token", session)
    assert len(result["records"]) == 1
    assert result["records"][0]["staffing"] == {"http_status": 403}
    assert result["wql_sources"] == {"http_status": 403}
    assert session.get.call_count == 4
    session.post.assert_not_called()
    for args in session.get.call_args_list:
        assert args.args[0].startswith("https://example.myworkday.com/api/")
        assert args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("path", ["https://evil.test/api/", "/api/../secret", "/api/workers?x=1"])
def test_discovery_rejects_uncontrolled_urls(path):
    session = transport()
    with pytest.raises(ValueError):
        read_json(tenant(), "test-token", session, path)
    session.get.assert_not_called()


def test_discovery_checks_size_and_identity():
    session = transport()
    response = session.get.return_value.__enter__.return_value
    response.iter_content.return_value = [b"x" * 2_000_001]
    with pytest.raises(ConnectionError, match="size limit"):
        read_json(tenant(), "test-token", session, "/api/test")
    with pytest.raises(ValueError, match="verified WID"):
        discover(tenant(), {"data": [{"id": "E0035"}]}, "test-token", session)


def test_wql_uses_discovered_aliases_and_resolves_manager(monkeypatch):
    calls = []
    source_id, manager_wid = "0" * 32, "b" * 32
    aliases = [
        "employeeID",
        "worker",
        "costCenter_ID",
        "FTE",
        "FTEPct",
        "managerID",
        "manager_EffectiveDated",
    ]

    def fake_read(tenant, token, session, path, params=None):
        calls.append((path, params))
        if path.endswith("/dataSources"):
            body = {"total": 1, "data": [{"id": source_id, "alias": "allWorkers"}]}
        elif path.endswith("/fields"):
            body = {
                "total": len(aliases),
                "data": [{"id": str(i), "alias": a} for i, a in enumerate(aliases)],
            }
        elif path.endswith("/data"):
            body = {
                "total": 1,
                "data": [{"employeeID": "0007", "manager_EffectiveDated": {"id": manager_wid}}],
            }
        elif path.endswith("/" + manager_wid):
            body = {"workerId": "0001"}
        else:
            body = {"workerId": "0007"}
        return {"http_status": 200, "body": body}

    monkeypatch.setattr("people_quality.workday_enrichment.read_json", fake_read)
    result = discover(tenant(), {"data": [{"id": "a" * 32}]}, "test-token", None)
    assert "FTE, FTEPct" in result["query"]
    assert "WHERE employeeID IN ('0007')" in result["query"]
    assert result["manager_references"][manager_wid]["body"]["workerId"] == "0001"
    calls.clear()
    discover(tenant(), {"data": [{"id": "a" * 32}]}, "test-token", None, result)
    assert not any(p.endswith("/fields") or p.endswith("/dataSources") for p, _ in calls)
