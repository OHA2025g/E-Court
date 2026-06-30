"""Task Management module — centralized constants and enums."""

TASK_STATUSES = [
    "DRAFT",
    "PROPOSED_BY_MEMBER",
    "PENDING_TEAM_LEAD_REVIEW",
    "UNASSIGNED",
    "ASSIGNED_TO_TEAM_LEAD",
    "ASSIGNED_TO_TEAM_MEMBER",
    "ACCEPTED",
    "IN_PROGRESS",
    "BLOCKED",
    "CLARIFICATION_REQUIRED",
    "RESOLVED",
    "SUBMITTED_FOR_APPROVAL",
    "REWORK_REQUIRED",
    "VERIFIED_BY_TEAM_LEAD",
    "MANAGER_APPROVAL_PENDING",
    "APPROVED_BY_MANAGER",
    "CLOSED",
    "REJECTED",
    "REASSIGNED",
    "ESCALATED",
    "SLA_BREACHED",
    "ON_HOLD",
    "CANCELLED",
    "DUPLICATE",
    "REOPENED",
]

STATUS_LABELS = {
    "DRAFT": "Draft",
    "PROPOSED_BY_MEMBER": "Proposed by Member",
    "PENDING_TEAM_LEAD_REVIEW": "Pending Team Lead Review",
    "UNASSIGNED": "Unassigned",
    "ASSIGNED_TO_TEAM_LEAD": "Assigned to Team Lead",
    "ASSIGNED_TO_TEAM_MEMBER": "Assigned to Team Member",
    "ACCEPTED": "Accepted",
    "IN_PROGRESS": "In Progress",
    "BLOCKED": "Blocked",
    "CLARIFICATION_REQUIRED": "Clarification Required",
    "RESOLVED": "Resolved",
    "SUBMITTED_FOR_APPROVAL": "Submitted for Approval",
    "REWORK_REQUIRED": "Rework Required",
    "VERIFIED_BY_TEAM_LEAD": "Verified by Team Lead",
    "MANAGER_APPROVAL_PENDING": "Manager Approval Pending",
    "APPROVED_BY_MANAGER": "Approved by Manager",
    "CLOSED": "Closed",
    "REJECTED": "Rejected",
    "REASSIGNED": "Reassigned",
    "ESCALATED": "Escalated",
    "SLA_BREACHED": "SLA Breached",
    "ON_HOLD": "On Hold",
    "CANCELLED": "Cancelled",
    "DUPLICATE": "Duplicate",
    "REOPENED": "Reopened",
}

PRIORITIES = ["Critical", "High", "Medium", "Low"]

DEFAULT_SLA_HOURS = {
    "Critical": 24,
    "High": 72,
    "Medium": 168,
    "Low": 360,
}

SLA_STATUSES = [
    "NOT_STARTED",
    "ON_TRACK",
    "AT_RISK",
    "BREACHED",
    "CLOSED_WITHIN_SLA",
    "CLOSED_AFTER_SLA",
]

EVIDENCE_TYPES = [
    "Document",
    "Screenshot",
    "Link",
    "System log",
    "Before/after proof",
    "Approval note",
    "Other",
]

EVIDENCE_VERIFICATION = ["Pending Review", "Verified", "Rejected", "Need More Evidence"]

APPROVAL_DECISIONS = ["Verified", "Rejected", "Need More Evidence", "Request Clarification", "Approved", "Rejected Closure"]

TASK_ROLES = ["manager", "team_lead", "team_member", "auditor", "admin"]

READONLY_STATUSES = {"CLOSED", "CANCELLED", "DUPLICATE"}

DEFAULT_CATEGORIES = [
    "Project Execution",
    "Infrastructure",
    "Compliance",
    "Support",
    "Documentation",
    "Integration",
]

SOURCE_TYPES = [
    "Manager Assigned",
    "Team Lead Assigned",
    "Member Proposed",
    "Self Task",
    "Issue Request",
    "Dependency",
    "Blocker",
    "Action Item",
    "Admin",
]

# Registered team + department pairs for Associated Team dropdown (seeded into tm_config).
DEFAULT_ASSOCIATED_TEAMS = [
    {"team": "PMU", "department": "Programme Management"},
    {"team": "PMU", "department": "Technical & Integration"},
    {"team": "PMU", "department": "Finance & Compliance"},
    {"team": "PMU", "department": "Infrastructure"},
    {"team": "e-Committee", "department": "Technical Review"},
    {"team": "e-Committee", "department": "Monitoring & Evaluation"},
    {"team": "CPC", "department": "High Court Coordination"},
    {"team": "CPC", "department": "Field Implementation"},
    {"team": "DoJ", "department": "Policy & Governance"},
    {"team": "DoJ", "department": "Cabinet Coordination"},
]


def format_associated_team_label(team: str, department: str) -> str:
    return f"{team} — {department}"
