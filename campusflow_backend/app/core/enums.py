"""
Enumerations aligned to the FINALIZED PostgreSQL schema.

The brief lists a rich appointment lifecycle (PENDING, APPROVED, REJECTED,
CONFIRMED, BUSY, RESCHEDULE_REQUIRED, CANCELLED, CHECKED_IN, IN_PROGRESS,
COMPLETED, NO_SHOW). The canonical `requests` table only permits:

    'Pending', 'Approved', 'Rejected', 'Cancelled', 'Rescheduled'

So this module keeps TWO layers and an explicit mapping between them:

  * RequestStatus  -> the committed states that live in requests.status
                      (exactly the 5 the schema allows).
  * QueueState     -> the OPERATIONAL sub-state that the schema cannot hold;
                      persisted in the additive queue_entries table.

LIFECYCLE_MAP documents, in one place, how each brief status is represented.
Nothing here invents a value the schema forbids.
"""
from __future__ import annotations

import enum


class Role(str, enum.Enum):
    """Role names exactly as seeded in the canonical `roles` table."""
    SUPER_ADMIN = "SuperAdmin"
    DEPARTMENT_ADMIN = "DepartmentAdmin"
    FACULTY = "Faculty"
    CLUB_LEAD = "ClubLead"
    STUDENT = "Student"


class RequestStatus(str, enum.Enum):
    """The ONLY values requests.status may hold (schema CHECK constraint)."""
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    RESCHEDULED = "Rescheduled"


REQUEST_STATUS_TERMINAL = frozenset({
    RequestStatus.REJECTED,
    RequestStatus.CANCELLED,
})


class RequestType(str, enum.Enum):
    """requests.request_type CHECK values."""
    APPOINTMENT = "Appointment"
    RECOMMENDATION_LETTER = "Recommendation Letter"
    PROJECT_APPROVAL = "Project Approval"
    GRADE_QUERY = "Grade Query"
    OTHER = "Other"


class QueueState(str, enum.Enum):
    """
    Operational sub-state held in the additive queue_entries table. These are
    the brief's live/post-approval statuses that requests.status cannot store.
    """
    WAITING = "WAITING"          # approved + token issued, not yet arrived
    CHECKED_IN = "CHECKED_IN"    # student physically checked in
    READY = "READY"             # next to be called
    IN_PROGRESS = "IN_PROGRESS"  # meeting started (started_at set)
    COMPLETED = "COMPLETED"      # meeting completed (completed_at set)
    NO_SHOW = "NO_SHOW"          # never checked in / grace expired
    WITHDRAWN = "WITHDRAWN"      # cancelled / superseded (e.g. faculty Busy)


QUEUE_TERMINAL = frozenset({
    QueueState.COMPLETED,
    QueueState.NO_SHOW,
    QueueState.WITHDRAWN,
})
QUEUE_ACTIVE = frozenset({
    QueueState.WAITING,
    QueueState.CHECKED_IN,
    QueueState.READY,
    QueueState.IN_PROGRESS,
})
# Eligible to be called next (must have physically arrived).
QUEUE_CALLABLE = frozenset({QueueState.CHECKED_IN, QueueState.READY})


class NotificationType(str, enum.Enum):
    """notifications.type CHECK values — only these four exist in the schema."""
    REQUEST_UPDATE = "REQUEST_UPDATE"
    EVENT_INVITATION = "EVENT_INVITATION"
    ALERT = "ALERT"
    SYSTEM = "SYSTEM"


class TokenType(str, enum.Enum):
    """tokens.token_type CHECK values (auth/access tokens, not queue tickets)."""
    API_KEY = "API_KEY"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    REQUEST_ACCESS = "REQUEST_ACCESS"


# ----------------------------------------------------------------------------
# Brief lifecycle -> concrete representation. Documented, not invented.
# ----------------------------------------------------------------------------
# value = (where it is stored, concrete value/notes)
LIFECYCLE_MAP: dict[str, tuple[str, str]] = {
    "PENDING":             ("requests.status", "Pending"),
    "APPROVED":            ("requests.status", "Approved"),
    "REJECTED":            ("requests.status", "Rejected"),
    # Approval and the pre-meeting availability confirmation are ONE step in
    # this MVP (see README). CONFIRMED therefore maps onto Approved.
    "CONFIRMED":           ("requests.status", "Approved (single-step; see README)"),
    # No 'Busy' request status exists. Busy is a faculty_busy_blocks row; any
    # affected request is set to 'Rescheduled' and its queue entry WITHDRAWN.
    "BUSY":                ("faculty_busy_blocks", "dated block + request->Rescheduled"),
    "RESCHEDULE_REQUIRED": ("requests.status", "Rescheduled"),
    "CANCELLED":           ("requests.status", "Cancelled"),
    "CHECKED_IN":          ("queue_entries.state", "CHECKED_IN"),
    "IN_PROGRESS":         ("queue_entries.state", "IN_PROGRESS + started_at"),
    "COMPLETED":           ("queue_entries.state", "COMPLETED + completed_at"),
    "NO_SHOW":             ("queue_entries.state", "NO_SHOW"),
}

DAYS_OF_WEEK = (
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
)
