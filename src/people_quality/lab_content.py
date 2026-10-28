"""Seeded guides and practice prompts; no claims of real stakeholder involvement."""

GUIDES = [
    (
        "audit-guide",
        "How to investigate an audit warning",
        "GPS",
        "Confirm the employee and reporting period. Compare permitted source records. Ask the "
        "field owner what applies on that date. Record evidence and propose an action. Obtain "
        "review before changing a record, then rerun validation. A warning is not proof of error.",
    ),
    (
        "payroll-faq",
        "Why might an employee be missing from payroll?",
        "Payroll",
        "Check employee versus contingent-worker scope, hire date, extract date and onboarding. "
        "An approved future hire may not belong in today's extract. "
        "Final pay may explain an active "
        "payroll record after termination. Confirm the payroll owner before correcting anything.",
    ),
    (
        "correction-checklist",
        "Checklist before applying a correction",
        "HR",
        "Confirm worker, field, source, effective date and approved evidence. Preview the change. "
        "A reviewer must approve the same proposal. "
        "Check the current old value before application. "
        "Revalidate the result and retain history. "
        "Editing a downloaded file does not update Workday.",
    ),
]

COACHING = {
    "timing": (
        "Payroll is dated yesterday and HR is dated today. What should you do first?",
        "Obtain comparable dated records and check integration timing before correction.",
    ),
    "approval": (
        "A reviewer approved a change. Does that prove it worked?",
        "No. Approval permits the action; validation checks the result after application.",
    ),
    "export": (
        "You corrected an exported spreadsheet. Is Workday now corrected?",
        "No. An export is a copy. Follow the source system's authorised correction process.",
    ),
}
