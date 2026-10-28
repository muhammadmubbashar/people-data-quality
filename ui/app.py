"""Local Streamlit client. Role switching is a demonstration, not enterprise login."""

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="People Data Quality", layout="wide")
st.title("People Data Quality and Payroll Readiness")
st.caption(
    "Independent portfolio demo • synthetic records • no Flight Centre or Workday integration"
)
role = st.sidebar.selectbox("Simulated identity", ["analyst", "reviewer", "operator"])
st.sidebar.info("Local role-key simulation. SSO and real individual identities are future work.")
base_url = os.getenv("API_URL", "http://127.0.0.1:8000")
headers = {"X-API-Key": os.getenv(f"{role.upper()}_KEY", "")}


def call(method, path, **kwargs):
    try:
        response = requests.request(method, base_url + path, headers=headers, timeout=15, **kwargs)
        if not response.ok:
            st.error(f"API returned {response.status_code}: {response.text}")
            st.stop()
        return response
    except requests.RequestException:
        st.error("API unavailable. Start scripts/run-api.ps1 in another terminal.")
        st.stop()


if role == "analyst" and st.button("Create synthetic audit run"):
    st.session_state["run"] = call("POST", "/runs/demo").json()["run_id"]
    st.rerun()
runs = call("GET", "/runs").json()
if not runs:
    st.info("Select analyst and create a synthetic audit run to begin.")
    st.stop()
run_ids = [r["id"] for r in runs]
run_id = st.selectbox("Audit run", run_ids)
tabs = st.tabs(["Audit queue", "Corrections and approvals", "Reports", "Help"])
findings = call("GET", f"/runs/{run_id}/findings").json()
with tabs[0]:
    open_items = [f for f in findings if f["status"] == "open"]
    st.metric("Open exception cases", len(open_items))
    st.dataframe(findings, width="stretch")
    if findings:
        selected = st.selectbox(
            "Investigate",
            findings,
            format_func=lambda f: f"{f['worker_id']} — {f['rule']} — {f['status']}",
        )
        st.write(selected["explanation"])
        st.json(call("GET", f"/runs/{run_id}/records/{selected['worker_id']}").json())
        if (
            role == "analyst"
            and selected["field"] == "cost_centre"
            and selected["status"] == "open"
        ):
            with st.form("correction"):
                value = st.selectbox("Proposed cost centre", ["C100", "C200", "C300"])
                reason = st.text_area("Evidence and reason (at least 10 characters)")
                if st.form_submit_button("Request review"):
                    result = call(
                        "POST",
                        "/changes",
                        json={"finding_id": selected["id"], "new_value": value, "reason": reason},
                    ).json()
                    st.success(f"Requested: {result['change_id']}")
with tabs[1]:
    changes = call("GET", "/changes").json()
    st.dataframe(changes, width="stretch")
    if changes:
        change = st.selectbox("Change", changes, format_func=lambda c: f"{c['id']} — {c['status']}")
        st.json(call("GET", f"/changes/{change['id']}/events").json())
        if role == "reviewer" and change["status"] == "pending" and st.button("Approve request"):
            call("POST", f"/changes/{change['id']}/approve")
            st.rerun()
        if (
            role == "operator"
            and change["status"] == "approved"
            and st.button("Apply and revalidate")
        ):
            call("POST", f"/changes/{change['id']}/apply")
            st.rerun()
with tabs[2]:
    st.write("Case counts and affected-worker counts have different denominators.")
    st.metric("Distinct affected workers", len({f["worker_id"] for f in open_items}))
    report = call("GET", f"/runs/{run_id}/report.csv")
    st.download_button("Download audit CSV", report.content, "synthetic-audit.csv", "text/csv")
    st.write("Native Workday report specification: docs/workday-report-spec.md")
with tabs[3]:
    st.subheader("Investigate before correcting")
    st.write(
        "1. Confirm scope and as-of date. 2. Compare source records. 3. Ask the field owner. "
        "4. Request approval with evidence. 5. Apply only an approved change. 6. Revalidate."
    )
    st.write(
        "Duplicates are quarantined from joins. A future hire or contingent worker can be "
        "legitimately absent from current payroll. Termination plus an active payroll record "
        "may represent final pay and requires context, not an automatic correction."
    )
    st.write(
        "Phase 1 supports cost-centre corrections. Batch previews are available via API docs. "
        "Other corrections, rejection/escalation, trend history and native Workday tasks "
        "are tracked in the roadmap."
    )
