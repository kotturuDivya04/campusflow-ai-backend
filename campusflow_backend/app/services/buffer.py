"""
Single source of truth for the meeting buffer (and a few related scheduling
numbers).

Resolution order (brief: "Read the buffer from an existing settings table if
available. Otherwise place it in clearly documented application configuration"):

    1. system_settings.APPOINTMENT_BUFFER_MINUTES   (canonical DB table)
    2. Settings.DEFAULT_BUFFER_MINUTES              (documented app config)

The same pattern is used for the default meeting length and the optional queue
break cadence so every consumer (free-slot engine, booking validation,
rescheduling, conflict checks, ETA) reads one consistent value.
"""
from __future__ import annotations

from app.core.config import settings
from app.repositories.repositories import SettingsRepository

BUFFER_KEY = "APPOINTMENT_BUFFER_MINUTES"
MEETING_KEY = "DEFAULT_MEETING_MINUTES"
BREAK_AFTER_KEY = "QUEUE_BREAK_AFTER"
BREAK_MINUTES_KEY = "QUEUE_BREAK_MINUTES"


class BufferPolicy:
    """Reads scheduling numbers, preferring system_settings over app config."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._repo = settings_repo

    def buffer_minutes(self) -> int:
        return self._repo.get_int(BUFFER_KEY, settings.DEFAULT_BUFFER_MINUTES)

    def meeting_minutes(self) -> int:
        return self._repo.get_int(MEETING_KEY, settings.DEFAULT_MEETING_MINUTES)

    def break_after(self) -> int:
        return self._repo.get_int(BREAK_AFTER_KEY, settings.QUEUE_BREAK_AFTER)

    def break_minutes(self) -> int:
        return self._repo.get_int(BREAK_MINUTES_KEY, settings.QUEUE_BREAK_MINUTES)
