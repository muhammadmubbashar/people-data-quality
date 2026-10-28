# Data contract and mock business policy

The v0.2 API accepts `as_of`, `workday`, `payroll`, and `core`. Each source is a nonempty list
of at most 5,000 worker records. This is an application limit, not a measured throughput claim.
Use the demo fixture as a JSON example. Real-platform names require an explicit adapter mapping.

Required identity: worker_id, a text ID preserving leading zeroes. Normalise surrounding whitespace
for matching. Model defaults exist for the fixture; a real-platform adapter must explicitly supply
all relevant fields and reject unmapped mandatory values rather than relying on defaults.

Fields: worker_type, status, cost_centre, manager_id, fte, hire_date and termination_date.
Dates use ISO YYYY-MM-DD. A blank termination date means no date supplied. Mock cost centres
are C100, C200 and C300; valid FTE is greater than zero and at most one.

All three extracts must represent the same agreed period and population. The optional source_dates object must supply exactly workday, payroll and core ISO dates.
If absent, the demo assumes each source is dated as_of. A mismatched date flags timing, suppresses
comparisons involving that source and blocks corrections. Full effective-dated event history,
extract timestamps and live late-arrival handling remain future adapter work.

Current mock HR status Active and worker_type Employee define the payroll comparison population.
Contingent workers and future hires are excluded. Leave and terminated workers are not automatically
classified as payroll defects; final-pay and leave rules need payroll-owner confirmation.
The JSON model rejects unknown status/type values; a future vendor adapter must explicitly map them.

Duplicate IDs are findings and are excluded from joins. A missing manager and a self-manager need
investigation. The CEO/root worker can have an empty manager. Cost-centre mismatches use the
current synthetic HR value as the assumed authority; the analyst must establish evidence before review.

Expected fixture: seven findings. IDs E0003, E0012, E0015, E0020, E0035, E0045 and E0050.
E0030 is a final-pay illustration, E0060 leave, E0080 contingent and E0090 future hire.


Original and current CSV exports include a manifest with source dates, policy and capture provenance.
The download is a ZIP of synthetic input files, not a native Workday report or Excel competency test.
Text that could be interpreted as a spreadsheet formula is escaped on export.
