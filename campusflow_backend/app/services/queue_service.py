"""
QueueService — the live token queue.

Responsibilities (brief):
  * reconstruct the live queue for a faculty from the database
  * student check-in
  * report delay
  * request a token exchange between two students
  * begin / complete a meeting, recording ACTUAL start and finish timestamps
  * expose current token, waiting tokens, completed tokens, delayed tokens
  * compute each waiting student's ETA

State is always derived from persisted queue_entries rows — never from process
memory — so a restart loses nothing and multiple workers stay consistent.
"""
from __future__ import annotations

import datetime as _dt

from app.core.enums import QueueState
from app.core.errors import (
    Conflict, NotFound, PermissionDenied, ValidationFailed,
)
from app.repositories.repositories import (
    QueueRepository, RequestRepository, SettingsRepository, SlotRepository,
)
from app.services import queue_logic, transitions
from app.services.buffer import BufferPolicy
from app.services.domain import ETAEstimate
from app.services.eta import estimate_eta
from app.notifications.service import NotificationService

UTC = _dt.timezone.utc


def _now() -> _dt.datetime:
    return _dt.datetime.now(UTC)


class QueueService:
    def __init__(
        self,
        *,
        queue: QueueRepository,
        requests: RequestRepository,
        slots: SlotRepository,
        settings_repo: SettingsRepository,
        notifications: NotificationService,
    ) -> None:
        self._queue = queue
        self._requests = requests
        self._slots = slots
        self._policy = BufferPolicy(settings_repo)
        self._notify = notifications

    # -- helpers ------------------------------------------------------------
    def _entry_or_404(self, entry_id: int):
        e = self._queue.by_id(entry_id)
        if e is None:
            raise NotFound(f"queue entry {entry_id} not found")
        return e

    def _views(self, rows) -> list:
        meeting = self._policy.meeting_minutes()
        views = []
        for r in rows:
            v = QueueRepository.to_view(r)
            v.effective_minutes = meeting
            views.append(v)
        return views

    # -- live queue ---------------------------------------------------------
    def live_queue(self, *, faculty_id: int, date: _dt.date) -> list[dict]:
        """Grouped by academic slot, in chronological slot order."""
        rows = self._queue.session_entries(faculty_id, date)
        by_slot: dict[int, list] = {}
        for r in rows:
            by_slot.setdefault(r.academic_slot_id, []).append(r)

        slot_order = {s.id: (s.start_time, s.slot_name) for s in self._slots.as_views()}
        out: list[dict] = []
        for slot_id in sorted(by_slot, key=lambda i: slot_order.get(i, (_dt.time.max, ""))):
            group = by_slot[slot_id]
            views = self._views(group)
            snap = queue_logic.build_snapshot(views)
            out.append({
                "faculty_id": faculty_id,
                "meeting_date": date,
                "academic_slot_id": slot_id,
                "current_token": snap.current.token_number if snap.current else None,
                "waiting_tokens": [e.token_number for e in snap.waiting],
                "completed_tokens": [e.token_number for e in snap.completed],
                "delayed_tokens": [e.token_number for e in snap.delayed],
                "entries": group,
            })
        return out

    # -- check-in -----------------------------------------------------------
    def check_in(self, *, entry_id: int, acting_student_id: int):
        entry = self._entry_or_404(entry_id)
        if entry.student_id != acting_student_id:
            raise PermissionDenied("not your token")
        transitions.check_queue(QueueState(entry.state), QueueState.CHECKED_IN)
        entry.state = QueueState.CHECKED_IN.value
        entry.checked_in_at = _now()
        self._notify.notify(
            user_id=entry.faculty_id, event_key="QUEUE_UPDATE",
            message=f"Token #{entry.token_number} checked in.",
        )
        return entry

    # -- delay --------------------------------------------------------------
    def report_delay(self, *, entry_id: int, acting_student_id: int, minutes: int):
        entry = self._entry_or_404(entry_id)
        if entry.student_id != acting_student_id:
            raise PermissionDenied("not your token")
        if entry.state not in (QueueState.WAITING.value, QueueState.CHECKED_IN.value,
                               QueueState.READY.value):
            raise Conflict("delay can only be reported before the meeting starts")
        if minutes <= 0:
            raise ValidationFailed("delay must be positive")
        entry.delay_minutes = int(entry.delay_minutes or 0) + int(minutes)
        self._notify.notify(
            user_id=entry.faculty_id, event_key="DELAY_RECORDED",
            message=f"Token #{entry.token_number} reported a {minutes} minute delay.",
        )
        return entry

    # -- token exchange -----------------------------------------------------
    def exchange(self, *, entry_id: int, other_entry_id: int, acting_student_id: int):
        a = self._entry_or_404(entry_id)
        b = self._entry_or_404(other_entry_id)
        if a.student_id != acting_student_id:
            raise PermissionDenied("not your token")
        if (a.faculty_id, a.meeting_date, a.academic_slot_id) != \
           (b.faculty_id, b.meeting_date, b.academic_slot_id):
            raise Conflict("tokens belong to different queue sessions")

        va, vb = QueueRepository.to_view(a), QueueRepository.to_view(b)
        ok, reason = queue_logic.can_exchange(va, vb)
        if not ok:
            raise Conflict(reason)

        # Swap token numbers WITHOUT tripping the
        # UNIQUE(faculty,date,slot,token_number) constraint mid-transaction.
        # A direct A<->B swap momentarily leaves two rows sharing a number; we
        # route through a negative sentinel (real token numbers are >= 1) with
        # a flush between each step so the DB never sees a duplicate.
        a_num, b_num = a.token_number, b.token_number
        a.token_number = -a.id
        self._queue.flush()
        b.token_number = a_num
        self._queue.flush()
        a.token_number = b_num
        a.exchanged_with_id, b.exchanged_with_id = b.id, a.id
        self._queue.flush()
        for e, other in ((a, b), (b, a)):
            self._notify.notify(
                user_id=e.student_id, event_key="TOKEN_EXCHANGE",
                message=f"Your queue token is now #{e.token_number} (exchanged).",
            )
        return a, b

    # -- meeting lifecycle --------------------------------------------------
    def begin_meeting(self, *, entry_id: int, acting_faculty_id: int):
        entry = self._entry_or_404(entry_id)
        if entry.faculty_id != acting_faculty_id:
            raise PermissionDenied("not your queue")
        rows = self._queue.session_entries(
            entry.faculty_id, entry.meeting_date, entry.academic_slot_id)
        if any(r.state == QueueState.IN_PROGRESS.value and r.id != entry.id for r in rows):
            raise Conflict("another meeting is already in progress for this slot")
        transitions.check_queue(QueueState(entry.state), QueueState.IN_PROGRESS)
        entry.state = QueueState.IN_PROGRESS.value
        entry.started_at = _now()          # ACTUAL start time
        self._notify.notify(
            user_id=entry.student_id, event_key="MEETING_STARTED",
            message=f"Your meeting (token #{entry.token_number}) has started.",
        )
        return entry

    def complete_meeting(self, *, entry_id: int, acting_faculty_id: int):
        entry = self._entry_or_404(entry_id)
        if entry.faculty_id != acting_faculty_id:
            raise PermissionDenied("not your queue")
        transitions.check_queue(QueueState(entry.state), QueueState.COMPLETED)
        entry.state = QueueState.COMPLETED.value
        entry.completed_at = _now()        # ACTUAL finish time
        self._notify.notify(
            user_id=entry.student_id, event_key="MEETING_COMPLETED",
            message=f"Your meeting (token #{entry.token_number}) is complete.",
        )
        # Nudge the next student.
        rows = self._queue.session_entries(
            entry.faculty_id, entry.meeting_date, entry.academic_slot_id)
        nxt = queue_logic.next_to_call(self._views(rows))
        if nxt is not None:
            self._notify.notify(
                user_id=nxt.student_id, event_key="MEETING_APPROACHING",
                message=f"You are next — token #{nxt.token_number}.",
            )
        return entry

    def mark_no_show(self, *, entry_id: int, acting_faculty_id: int):
        entry = self._entry_or_404(entry_id)
        if entry.faculty_id != acting_faculty_id:
            raise PermissionDenied("not your queue")
        transitions.check_queue(QueueState(entry.state), QueueState.NO_SHOW)
        entry.state = QueueState.NO_SHOW.value
        self._notify.notify(
            user_id=entry.student_id, event_key="QUEUE_UPDATE",
            message=f"Token #{entry.token_number} was marked as a no-show.",
        )
        return entry

    # -- ETA ----------------------------------------------------------------
    def eta_for(self, *, entry_id: int) -> ETAEstimate:
        entry = self._entry_or_404(entry_id)
        rows = self._queue.session_entries(
            entry.faculty_id, entry.meeting_date, entry.academic_slot_id)
        views = self._views(rows)
        target = next((v for v in views if v.id == entry.id), None)
        if target is None:
            raise NotFound("queue entry not in its own session")
        in_progress = next(
            (v for v in views if v.state == QueueState.IN_PROGRESS.value), None)
        return estimate_eta(
            target=target,
            all_active=views,
            now=_now(),
            default_meeting_minutes=self._policy.meeting_minutes(),
            buffer_minutes=self._policy.buffer_minutes(),
            in_progress=in_progress,
            break_after=self._policy.break_after(),
            break_minutes=self._policy.break_minutes(),
        )

    def token_view(self, *, entry_id: int, acting_student_id: int) -> dict:
        entry = self._entry_or_404(entry_id)
        if entry.student_id != acting_student_id:
            raise PermissionDenied("not your token")
        eta = self.eta_for(entry_id=entry_id)
        return {
            "token_number": entry.token_number,
            "state": entry.state,
            "position_ahead": eta.position_ahead,
            "estimated_wait_minutes": eta.estimated_minutes,
            "eta_source": "UNAVAILABLE" if eta.unavailable else eta.calculation_source,
        }
