"""Small workspaces with plain-language task guidance."""

from datetime import date

import streamlit as st

TEAMS = ["HR", "Payroll", "GPS", "Workday support", "Finance"]
CAUSES = ["Unknown", "Data entry", "Integration timing", "Mapping", "Missing approval", "Training"]


def selected_run(call):
    runs = call("GET", "/runs").json()
    if not runs:
        st.info("Create a practice dataset in Practice setup first.")
        return None
    return st.selectbox(
        "Choose audit run", runs, format_func=lambda r: f"{r['as_of']} — {r['id']}"
    )["id"]


def case_workspace(call, finding, role):
    with st.expander("Investigation notes, owner and escalation"):
        case = call("GET", f"/lab/cases/{finding['id']}").json()
        st.write("Assign the next step to a team. Record what you know and what remains uncertain.")
        st.caption(f"Current case state: {case['state']} · version {case['version']}")
        if role == "analyst" and finding["status"] == "open":
            with st.form("case-notes"):
                owner = st.selectbox("Responsible team", TEAMS, index=TEAMS.index(case["owner"]))
                priority = st.selectbox(
                    "Priority",
                    ["low", "medium", "high"],
                    index=["low", "medium", "high"].index(case["priority"]),
                )
                state = st.selectbox(
                    "Next case state", ["investigating", "waiting", "escalated", "closed_no_change"]
                )
                cause = st.selectbox("Root cause", CAUSES, index=CAUSES.index(case["root_cause"]))
                evidence = st.text_area("Evidence and uncertainty", value=case["evidence"])
                action = st.text_input("Next action", value=case["next_action"])
                due = st.date_input("Follow-up date", date.fromisoformat(case["due_date"]))
                if st.form_submit_button("Save investigation"):
                    call(
                        "PUT",
                        f"/lab/cases/{finding['id']}",
                        json={
                            "owner": owner,
                            "priority": priority,
                            "state": state,
                            "root_cause": cause,
                            "evidence": evidence,
                            "next_action": action,
                            "due_date": due.isoformat(),
                            "expected_version": case["version"],
                        },
                    )
                    st.rerun()
        else:
            st.json(case)
        events = call("GET", f"/lab/events/{finding['id']}").json()
        if events:
            st.dataframe(events, hide_index=True, width="stretch")


def bulk(call, role):
    st.header("Correct several records with one reviewed proposal")
    st.write("Preview first. The whole batch must pass before any record is saved.")
    if role == "analyst":
        run = selected_run(call)
        if not run:
            return
        findings = call("GET", f"/runs/{run}/findings").json()
        eligible = [
            f
            for f in findings
            if f["status"] == "open"
            and f["field"] in {"cost_centre", "fte", "manager_id", "hire_date"}
        ]
        chosen = st.multiselect(
            "Findings to correct",
            eligible,
            format_func=lambda f: f"{f['worker_id']} / {f['source']} / {f['field']}",
        )
        items = []
        for finding in chosen:
            default = {"fte": "1.0", "manager_id": "E0001", "hire_date": "2026-01-01"}.get(
                finding["field"], "C100"
            )
            value = st.text_input(
                f"New value for {finding['worker_id']} {finding['field']}",
                default,
                key=f"batch-{finding['id']}",
            )
            items.append({"finding_id": finding["id"], "new_value": value})
        reason = st.text_area("Evidence supporting the whole batch")
        body = {"items": items, "reason": reason}
        if st.button("Preview batch", disabled=not items):
            preview = call("POST", "/lab/batches/preview", json=body).json()
            st.dataframe(preview["items"], hide_index=True, width="stretch")
            st.success(
                f"Preview only: {preview['before_count']} → {preview['after_count']} findings. "
                "No writes."
            )
        if st.button("Submit batch for review", disabled=not items):
            result = call("POST", "/lab/batches", json=body).json()
            st.success(f"Batch {result['id']} is pending review.")
    batches = call("GET", "/lab/batches").json()
    if batches:
        batch = st.selectbox(
            "Review a batch", batches, format_func=lambda b: f"{b['id']} — {b['status']}"
        )
        st.write(batch["proposal"]["reason"])
        st.dataframe(batch["proposal"]["items"], hide_index=True, width="stretch")
        reason = st.text_input("Review or application note", key="batch-review-reason")
        actions = []
        if batch["status"] == "pending":
            actions = (
                ["approve", "reject"]
                if role == "reviewer"
                else ["cancel"]
                if role == "analyst"
                else []
            )
        elif batch["status"] == "approved" and role == "operator":
            actions = ["apply"]
        elif batch["status"] == "approved" and role == "analyst":
            actions = ["cancel"]
        for action in actions:
            if st.button(f"{action.title()} batch"):
                call("POST", f"/lab/batches/{batch['id']}/{action}", json={"reason": reason})
                st.rerun()
        history = call("GET", f"/lab/events/{batch['id']}").json()
        st.dataframe(history, hide_index=True, width="stretch")


def reports(call, role):
    st.header("Reports and recurring problems")
    with st.expander("How would I plan the equivalent report in Workday?"):
        st.write(
            "Agree the purpose, date, population and permitted audience first. Ask the report "
            "owner which approved data source and security domain to use. Specify worker ID, "
            "status, type, cost centre, manager, FTE and relevant effective dates. Validate known "
            "examples and totals before sharing. Actual fields and report permissions depend "
            "on the tenant. This screen is a planning exercise, not a native Workday report."
        )
    run = selected_run(call)
    if not run:
        return
    source = st.selectbox("Source filter", ["All", "workday", "payroll", "core"])
    status = st.selectbox("Status filter", ["All", "open", "resolved", "closed_no_change"])
    rule = st.text_input("Rule filter (optional)")
    params = {
        k: v
        for k, v in {"source": source, "status": status, "rule": rule}.items()
        if v and v != "All"
    }
    report = call("GET", f"/lab/reports/{run}", params=params).json()
    st.metric("Open cases in this selection", report["open_cases"])
    st.write(
        f"{report['affected_workers']} distinct affected workers; "
        f"{report['distinct_hr_workers']} distinct HR worker IDs in this run."
    )
    st.write("Source dates", report["source_dates"])
    st.dataframe(
        report["rows"],
        column_order=[
            "worker_id",
            "rule",
            "source",
            "observed",
            "expected",
            "status",
            "root_cause",
            "explanation",
            "id",
        ],
        hide_index=True,
        width="stretch",
    )
    if report["by_root_cause"]:
        st.write("Recorded root causes (Unknown means not yet established)")
        st.bar_chart(
            [
                {"root_cause": key, "open_cases": value}
                for key, value in report["by_root_cause"].items()
            ],
            x="root_cause",
            y="open_cases",
            x_label="Root cause",
            y_label="Open cases",
        )
    export_view = st.selectbox("Excel practice source", ["captured", "current"])
    archive = call("GET", f"/lab/exports/{run}.zip", params={"view": export_view})
    st.download_button(
        "Download three source files for Excel",
        archive.content,
        "synthetic-excel-practice.zip",
        "application/zip",
    )
    st.subheader("Initial findings over time")
    trend = call("GET", "/lab/trends").json()
    st.caption(trend["basis"])
    for group in trend["groups"]:
        st.write(group["cohort"])
        comparable = [p for p in group["points"] if p["comparable"]]
        if comparable:
            st.dataframe(comparable, hide_index=True, width="stretch")
            if len(comparable) > 1:
                st.line_chart(
                    comparable,
                    x="as_of",
                    y="initial_findings",
                    x_label="Snapshot date",
                    y_label="Initial exception cases",
                )
        if any(not p["comparable"] for p in group["points"]):
            st.warning("A mismatched-date capture is excluded from the trend chart.")
    st.caption(
        "These are measured synthetic findings, "
        "not evidence of business savings or live performance."
    )


def testing(call, role):
    st.header("Release testing and defects")
    st.write("A release is a version of a system. Check that old tasks still work after a change.")
    if role == "analyst":
        release = st.selectbox("Practice release", ["stable", "candidate_bug", "candidate_fixed"])
        if st.button("Run acceptance and regression checks"):
            result = call("POST", "/lab/test-runs", json={"release": release}).json()
            st.session_state["test_run"] = result["id"]
    runs = call("GET", "/lab/test-runs").json()
    if runs:
        test = st.selectbox(
            "Test evidence", runs, format_func=lambda r: f"{r['release']} — {r['id']}"
        )
        st.write("Suite passed" if test["passed"] else "Suite failed: investigate before release")
        st.dataframe(
            test["results"],
            column_order=["name", "passed", "expected", "actual", "description"],
            hide_index=True,
            width="stretch",
        )
        failed = [r for r in test["results"] if not r["passed"]]
        if failed and role == "analyst":
            failed_case = st.selectbox("Failed case", failed, format_func=lambda r: r["name"])
            with st.form("defect"):
                impact = st.text_input("Who is affected and how?")
                steps = st.text_area("Steps to reproduce")
                if st.form_submit_button("Log defect"):
                    call(
                        "POST",
                        "/lab/defects",
                        json={
                            "test_run_id": test["id"],
                            "case_name": failed_case["name"],
                            "impact": impact,
                            "steps": steps,
                        },
                    )
                    st.rerun()
    defects = call("GET", "/lab/defects").json()
    if defects:
        defect = st.selectbox(
            "Defect", defects, format_func=lambda d: f"{d['case_name']} — {d['status']} — {d['id']}"
        )
        st.write(f"Status: {defect['status']} · affected scenario: {defect['case_name']}")
        st.write("Impact:", defect["impact"])
        st.write("Steps and observed behaviour:", defect["steps"])
        with st.expander("Technical defect evidence"):
            st.json(defect)
        passing = [r for r in runs if r["passed"]]
        if role == "reviewer" and defect["status"] == "open" and passing:
            retest = st.selectbox(
                "Passing retest", passing, format_func=lambda r: f"{r['release']} — {r['id']}"
            )
            note = st.text_input("Resolution evidence")
            if st.button("Verify retest and resolve defect"):
                call(
                    "POST",
                    f"/lab/defects/{defect['id']}/resolve",
                    json={
                        "passing_test_run_id": retest["id"],
                        "reason": note,
                        "expected_version": defect["version"],
                    },
                )
                st.rerun()
    st.caption(
        "This exercises fictional releases of this application, not actual Workday releases."
    )


def knowledge(call, role):
    st.header("Guides and coaching")
    query = st.text_input("Search the knowledge base")
    articles = call("GET", "/lab/articles", params={"q": query}).json()
    for article in articles:
        with st.expander(f"{article['title']} — version {article['version']}"):
            st.write(article["body"])
            st.caption(f"Owner: {article['audience']}; review date: {article['review_date']}")
            if role == "analyst":
                with st.form(f"article-{article['id']}"):
                    body = st.text_area("Updated guide", article["body"])
                    review = st.date_input(
                        "Review date", date.fromisoformat(article["review_date"])
                    )
                    if st.form_submit_button("Save a new version"):
                        call(
                            "PUT",
                            f"/lab/articles/{article['id']}",
                            json={
                                "title": article["title"],
                                "audience": article["audience"],
                                "body": body,
                                "review_date": review.isoformat(),
                                "expected_version": article["version"],
                            },
                        )
                        st.rerun()
            versions = call("GET", f"/lab/documents/article/{article['id']}/versions").json()
            st.caption(f"{len(versions)} retained versions")
    coaching = call("GET", "/lab/coaching").json()
    st.subheader("Explain a finding to another person")
    if role == "analyst":
        prompt = st.selectbox(
            "Coaching question",
            list(coaching["prompts"]),
            format_func=lambda k: coaching["prompts"][k][0],
        )
        with st.form("coaching"):
            kind = st.selectbox("Evidence type", ["self_practice", "peer_feedback"])
            alias = st.text_input("Learner alias (no personal details)", "Practice learner")
            answer = st.text_area("Learner's explanation")
            feedback = st.text_area("Feedback and improvement")
            if st.form_submit_button("Record practice session"):
                call(
                    "POST",
                    "/lab/coaching",
                    json={
                        "evidence_kind": kind,
                        "learner_alias": alias,
                        "question": prompt,
                        "answer": answer,
                        "feedback": feedback,
                    },
                )
                st.rerun()
        with st.expander("Compare with a model explanation"):
            st.write(coaching["prompts"][prompt][1])
    if coaching["sessions"]:
        st.dataframe(coaching["sessions"], hide_index=True, width="stretch")
    st.caption("Recording self-practice does not establish that you coached a real HR colleague.")


def requirements(call, role):
    st.header("Requirements workshop")
    st.write("Agree what problem matters, who owns it and how you will know a solution works.")
    rows = call("GET", "/lab/requirements").json()
    if role == "analyst":
        with st.form("requirement"):
            title = st.text_input("Requirement title")
            team = st.selectbox("Requesting team", TEAMS)
            problem = st.text_area("Business problem")
            criteria = st.text_area("Acceptance criteria: Given / When / Then")
            decision = st.text_area("Agreed decision, assumptions and open questions")
            kind = st.selectbox("Workshop evidence", ["self_practice", "peer_workshop"])
            if st.form_submit_button("Propose requirement"):
                import uuid

                call(
                    "PUT",
                    f"/lab/requirements/{uuid.uuid4()}",
                    json={
                        "title": title,
                        "team": team,
                        "business_problem": problem,
                        "acceptance_criteria": criteria,
                        "decision": decision,
                        "evidence_kind": kind,
                        "expected_version": 0,
                    },
                )
                st.rerun()
    if rows:
        requirement = st.selectbox(
            "Requirement", rows, format_func=lambda r: f"{r['title']} — {r['status']}"
        )
        st.json(requirement)
        if role == "reviewer" and requirement["status"] == "proposed":
            reason = st.text_input("Review decision and reason")
            if st.button("Accept requirement"):
                call(
                    "POST",
                    f"/lab/requirements/{requirement['id']}/accept",
                    json={"reason": reason, "expected_version": requirement["version"]},
                )
                st.rerun()
    st.caption(
        "A simulated workshop is practice. An actual peer session needs actual participation."
    )


def setup(call, role):
    st.header("Start a practice exercise")
    st.write(
        "All datasets are fictional. Existing runs and your earlier E0035 lesson are preserved."
    )
    if role == "analyst":
        if st.button("Create fresh seven-finding dataset"):
            result = call("POST", "/runs/demo").json()
            st.success(f"Created run {result['run_id']}. Open My work to investigate it.")
        if st.button("Create three dated captures for trends"):
            result = call("POST", "/lab/practice-history").json()
            st.dataframe(result["runs"], hide_index=True, width="stretch")
        if st.button("Create mismatched-date investigation"):
            result = call("POST", "/lab/timing-scenario").json()
            st.success(f"Created run {result['run_id']}. Payroll is dated one day earlier.")
    st.subheader("Your practice route")
    st.write(
        "1. Investigate and assign a case. 2. Preview and review a bulk correction. "
        "3. Compare dated reports. 4. Catch a faulty release and record a defect. "
        "5. Teach a finding. 6. Agree a requirement."
    )
    st.write(
        "Real Workday reports, permissions, release testing and API connections still require "
        "authorised access. This lab reproduces the learning workflow, "
        "not Flight Centre's software."
    )


def render_workspace(name, call, role):
    views = {
        "Bulk corrections": bulk,
        "Reports and trends": reports,
        "Release testing": testing,
        "Guides and coaching": knowledge,
        "Requirements workshop": requirements,
        "Practice setup": setup,
    }
    views[name](call, role)
