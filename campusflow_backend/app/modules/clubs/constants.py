"""Constants used across the Clubs module."""
from __future__ import annotations

from datetime import timezone

EVENT_STATUSES = {
    "Draft",
    "Pending Approval",
    "Approved",
    "Rejected",
    "Cancelled",
}

EVENT_OPEN_STATUSES = {"Approved"}

BOOKING_STATUSES = {
    "Pending",
    "Approved",
    "Rejected",
    "Cancelled",
}

REGISTRATION_STATUSES = {"Registered", "Cancelled"}
ATTENDANCE_STATUSES = {"Present", "Absent"}
ANNOUNCEMENT_TARGETS = {
    "ALL_MEMBERS",
    "PARTICIPANTS",
    "FACULTY",
    "COORDINATORS",
}
DEFAULT_ANNOUNCEMENT_TARGET = "ALL_MEMBERS"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
UTC = timezone.utc
