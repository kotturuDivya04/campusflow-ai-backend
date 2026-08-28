"""Validation helpers for the Clubs module."""
from __future__ import annotations

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.clubs.constants import (
    ANNOUNCEMENT_TARGETS,
    EVENT_STATUSES,
    REGISTRATION_STATUSES,
    ATTENDANCE_STATUSES,
    BOOKING_STATUSES,
)
from app.modules.clubs.repository import ClubRepository, EventRepository


def validate_club_name_uniqueness(club_repo: ClubRepository, name: str) -> None:
    if club_repo.by_name(name) is not None:
        raise Conflict(f"club with name '{name}' already exists")


def validate_club_category(category: str) -> None:
    if category not in {"Technical", "Cultural", "Sports", "Social", "Academic"}:
        raise ValidationFailed(f"invalid club category '{category}'")


def validate_event_status(status: str | None) -> str:
    meta = status or "Draft"
    if meta not in EVENT_STATUSES:
        raise ValidationFailed(f"invalid event status '{meta}'")
    return meta


def validate_event_exists(event_repo: EventRepository, event_id: int):
    event = event_repo.by_id(event_id)
    if event is None:
        raise NotFound(f"event {event_id} not found")
    return event


def validate_announcement_target(target: str) -> None:
    if target not in ANNOUNCEMENT_TARGETS:
        raise ValidationFailed(f"invalid announcement target '{target}'")


def validate_registration_status(status: str) -> None:
    if status not in REGISTRATION_STATUSES:
        raise ValidationFailed(f"invalid registration status '{status}'")


def validate_attendance_status(status: str) -> None:
    if status not in ATTENDANCE_STATUSES:
        raise ValidationFailed(f"invalid attendance status '{status}'")


def validate_booking_status(status: str | None) -> str:
    resolved = status or "Pending"
    if resolved not in BOOKING_STATUSES:
        raise ValidationFailed(f"invalid booking status '{resolved}'")
    return resolved
