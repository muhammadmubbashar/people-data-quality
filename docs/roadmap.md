# Requirements and staged delivery

Work in small PRs. Completed below means local implementation with tests, not real Workday operation.

## Phase 1 — Working local foundation

- [x] Audit queue and understandable findings.
- [x] Source-record comparison and documented policy.
- [x] Cost-centre correction request, separate review and application.
- [x] Stale-value protection, revalidation and repeat-application protection.
- [x] Bulk preview API with no writes; complete execution added in v0.2.
- [x] CSV report and basic help.
- [x] Domain/API regression tests, locked dependencies and CI definition.
- [x] Architecture and production gap documentation.

## Phase 2 — Real platform and analyst tools

- [ ] Obtain personal Workday tenant; verify actual products and permissions.
- [ ] Capture authorised synthetic worker report and actual data dictionary.
- [ ] CSV adapter: mandatory mappings, key uniqueness, encoding, row/size limits and provenance.
- [ ] Contract tests against an actual permitted sample export, with no credentials in fixtures.
- [ ] Excel/Power Query exercise and user teaching walkthrough.
- [ ] Native report configuration evidence if tenant permissions allow it.
- [ ] Implement an authenticated read-only API adapter only after discovering supported endpoints.

## Phase 3 — Complete the advertised operational workflow

- [ ] User coaching: record an actual peer walkthrough, feedback and guide revision.
- [x] Root-cause investigation notes, case ownership and escalation.
- [x] Correction rejection, cancellation and additional approved field types.
- [x] Whole-batch approval/execution with atomic validation and rollback evidence.
- [x] Compare source snapshot dates and reject unknown JSON status/type values.
- [ ] Real-platform effective-date history, extract timestamps and approved vendor mappings.
- [x] Reporting filters, captured/current source exports and native report planning notes.
- [ ] Workday-native report configuration evidence in an authorised tenant.
- [x] Recurring-issue trends across comparable snapshots with explicit denominators.
- [x] Simulated release change, failing regression, defect log and successful retest.
- [x] Versioned user guides, correction checklist, FAQs and reporting ownership.
- [ ] Requirements workshop with an actual willing participant; record decisions and uncertainties.

## Phase 4 — Production engineering proof

- [ ] Individual SSO, scoped access and independent approvals.
- [ ] PostgreSQL repository, versioned migrations and recovery test.
- [ ] Bounded imports, asynchronous jobs, paging and measured load tests.
- [ ] Monitoring, protected audit storage, retention and incident drills.
- [ ] Staging deployment, rollback rehearsal and an approved release gate.

## Definition of done for each feature

Write the business problem and acceptance criteria first. Add a failing meaningful test, implement,
run checks, update the guide, capture actual evidence and review the PR. Mock and real-platform
tests have separate labels. No performance or business-impact claims without measurements.


## v0.2 evidence boundaries

Coaching and requirements workflows are implemented; actual participation is still a separate task.
Three-source CSV export supports an Excel exercise; it does not prove Excel skill or import arbitrary
Workday exports. Simulated releases test this application's rules, not a real Workday tenant.
All production engineering and real platform integration remain explicitly future work.
