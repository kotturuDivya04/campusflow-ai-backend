"""
Injectable clock (reused from the original backend, unchanged in spirit).

No service reads the wall clock directly; every time reference flows through a
Clock. SystemClock is the only place a real now() is read; VirtualClock lets
tests drive time deterministically. All timestamps are timezone-aware (UTC),
satisfying the brief's "use timezone-aware timestamps" rule.
"""
from __future__ import annotations

import datetime as _dt
from typing import Protocol


class Clock(Protocol):
    def now(self) -> _dt.datetime: ...


class SystemClock:
    def now(self) -> _dt.datetime:
        return _dt.datetime.now(_dt.timezone.utc)


class VirtualClock:
    def __init__(self, start: _dt.datetime | None = None) -> None:
        self._now = start or _dt.datetime(2026, 1, 1, 9, 0, 0, tzinfo=_dt.timezone.utc)

    def now(self) -> _dt.datetime:
        return self._now

    def advance(self, *, minutes: int = 0, seconds: int = 0) -> _dt.datetime:
        self._now += _dt.timedelta(minutes=minutes, seconds=seconds)
        return self._now

    def set(self, when: _dt.datetime) -> None:
        self._now = when
