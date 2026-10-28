"""Exercise the real UI against the real API contract without network or credentials."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from people_quality.api import Settings, create_app


@pytest.mark.parametrize(
    "workspace",
    [
        "Bulk corrections",
        "Reports and trends",
        "Release testing",
        "Guides and coaching",
        "Requirements workshop",
        "Practice setup",
    ],
)
def test_expanded_workspaces_render(monkeypatch, tmp_path, workspace):
    keys = {role: role + "-ui-test-" + "x" * 32 for role in ("analyst", "reviewer", "operator")}
    for role, value in keys.items():
        monkeypatch.setenv(f"{role.upper()}_KEY", value)
    with TestClient(create_app(Settings(str(tmp_path / "ui.db"), keys))) as api:
        headers = {"X-API-Key": keys["analyst"]}
        api.post("/lab/practice-history", headers=headers).raise_for_status()
        api.post("/lab/test-runs", headers=headers, json={"release": "candidate_bug"})

        def transport(method, url, **kwargs):
            kwargs.pop("timeout", None)
            response = api.request(method, urlsplit(url).path, **kwargs)
            response.ok = response.is_success
            return response

        monkeypatch.setattr("requests.request", transport)
        app = AppTest.from_file(str(Path(__file__).parents[1] / "ui/app.py"), default_timeout=60)
        app.run()
        app.sidebar.selectbox[1].set_value(workspace).run()
        assert not app.exception
        assert app.header


def test_ui_request_review_apply_workflow(monkeypatch, tmp_path):
    keys = {role: role + "-ui-test-" + "x" * 32 for role in ("analyst", "reviewer", "operator")}
    for role, value in keys.items():
        monkeypatch.setenv(f"{role.upper()}_KEY", value)
    with TestClient(create_app(Settings(str(tmp_path / "ui.db"), keys))) as api:

        def transport(method, url, **kwargs):
            kwargs.pop("timeout", None)
            response = api.request(method, urlsplit(url).path, **kwargs)
            # requests.Response and httpx.Response have different success attributes.
            response.ok = response.is_success
            return response

        monkeypatch.setattr("requests.request", transport)
        app = AppTest.from_file(str(Path(__file__).parents[1] / "ui/app.py"), default_timeout=60)
        app.run()
        assert not app.exception
        app.button[0].click().run()
        assert not app.exception
        assert app.metric[0].value == "7"
        investigate = next(w for w in app.selectbox if w.label == "Investigate")
        run_id = api.get("/runs", headers={"X-API-Key": keys["analyst"]}).json()[0]["id"]
        cases = api.get(f"/runs/{run_id}/findings", headers={"X-API-Key": keys["analyst"]}).json()
        investigate.set_value(next(c for c in cases if c["worker_id"] == "E0035")).run()
        app.text_area[0].set_value("Confirmed synthetic HR record shows C100.")
        next(b for b in app.button if b.label == "Request review").click().run()
        assert not app.exception
        app.sidebar.selectbox[0].set_value("reviewer").run()
        next(b for b in app.button if b.label == "Approve request").click().run()
        assert not app.exception
        app.sidebar.selectbox[0].set_value("operator").run()
        next(b for b in app.button if b.label == "Apply and revalidate").click().run()
        assert not app.exception
        assert app.metric[0].value == "6"
