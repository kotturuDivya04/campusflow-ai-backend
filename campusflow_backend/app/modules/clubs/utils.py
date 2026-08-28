"""Utility functions for the Clubs module."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.errors import ValidationFailed
from app.modules.clubs.constants import MAX_PAGE_SIZE, DEFAULT_PAGE_SIZE


def current_time_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_pagination(page: int | None, size: int | None) -> tuple[int, int]:
    page = page or 1
    size = size or DEFAULT_PAGE_SIZE
    if page < 1:
        raise ValidationFailed("page must be at least 1")
    if size < 1 or size > MAX_PAGE_SIZE:
        raise ValidationFailed(f"size must be between 1 and {MAX_PAGE_SIZE}")
    return page, size


def pagination_offset(page: int, size: int) -> int:
    return (page - 1) * size


def validate_time_window(start_time: datetime, end_time: datetime) -> None:
    if start_time >= end_time:
        raise ValidationFailed("start_time must be before end_time")


def validate_future_event(start_time: datetime) -> None:
    if start_time <= current_time_utc():
        raise ValidationFailed("event must start in the future")


def overlap(start_time: datetime, end_time: datetime,
            other_start: datetime, other_end: datetime) -> bool:
    return start_time < other_end and other_start < end_time
