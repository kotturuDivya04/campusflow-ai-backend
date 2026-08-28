"""
AppointmentService — the appointment/request workflow orchestrator.

Implements the brief's required workflow end to end:
  submit -> validate -> reject duplicates -> save pending -> notify faculty
  approve (single step; = CONFIRMED) -> access token + queue entry -> notify
  reject -> notify with reason
  reschedule -> store new dated slot -> notify
  mark busy -> block dated slot + reconcile affected requests -> notify
  cancel (student) -> withdraw

=== Schema limitation & how a "dated slot" is stored =======================
The canonical `requests` table has no academic_slot_id and no separate date
column — only `scheduled_time TIMESTAMPTZ`. So a request's requested (date, slot)
is encoded as:

    scheduled_time = datetime.combine(date, slot.start_time, tzinfo=UTC)

Recovery matches scheduled_time.date() -> meeting_date and scheduled_time.time()
-> the academic_slots row with that start_time (slot start times are distinct in
the seeded schema). Once approved, the authoritative (date, slot) lives on the
additive queue_entries row. This compromise is documented in
SCHEMA_CAPABILITY_MAP.md.

All multi-step mutations run inside the request-scoped transaction; the caller
(route) commits once on success, rolls back on error.
"""
from __future__ import annotations

import datetime as _dt

from app.core.enums import QueueState, RequestStatus, RequestType
from app.core.errors import (
    Conflict, DuplicateRequest, NotFound, PermissionDenied, SlotUnavailable,
    ValidationFailed,
)
from app.repositories.repositories import (
    BusyRepository, FacultyRepository, QueueRepository, RequestRepository,
    SlotRepository, StudentRepository,
)
from app.services import priority, transitions
from app.services.domain import QueueEntryView, SlotView
from app.services.free_slot_service import FreeSlotService
from app.services.token_service import TokenService
from app.notifications.service import NotificationService

UTC = _dt.timezone.utc


def _encode_scheduled(date: _dt.date, slot: SlotView) -> _dt.datetime:
    return _dt.datetime.combine(date, slot.start_time, tzinfo=UTC)


class AppointmentService:
    def __init__(
        self,
        *,
        requests: RequestRepository,
        queue: QueueRepository,
        faculty: FacultyRepository,
        students: StudentRepository,
        slots: SlotRepository,
        busy: BusyRepository,
        free_slots: FreeSlotService,
        tokens: TokenService,
        notifications: NotificationService,
    ) -> None:
        self._requests = requests
        self._queue = queue
        self._faculty = faculty
        self._students = students
        self._slots = slots
        self._busy = busy
        self._free = free_slots
        self._tokens = tokens
        self._notify = notifications

    # -- helpers ------------------------------------------------------------
    def _slot_or_404(self, slot_id: int) -> SlotView:
        s = self._slots.by_id(slot_id)
        if s is None:
            raise NotFound(f"academic slot {slot_id} not found")
        return SlotView(s.id, s.slot_name, s.start_time, s.end_time)

    def _resolve_dated_slot(self, request) -> tuple[_dt.date | None, SlotView | None]:
        if request.scheduled_time is None:
            return None, None
        sched = request.scheduled_time
        if sched.tzinfo is not None:
            sched = sched.astimezone(UTC)
        want = sched.time().replace(microsecond=0)
        for s in self._slots.as_views():
            if s.start_time.replace(microsecond=0) == want:
                return sched.date(), s
        return sched.date(), None

    # -- 1) submit ----------------------------------------------------------
    def submit(
    self, *, student_id: int, faculty_id: int, date: _dt.date, slot_id: int,
    title: str, description: str,
    request_type: str = RequestType.APPOINTMENT.value,
    duration_minutes: int = 50,
):
        if self._students.by_id(student_id) is None:
            raise NotFound(f"student {student_id} not found")
        if self._faculty.by_id(faculty_id) is None:
            raise NotFound(f"faculty {faculty_id} not found")
        slot = self._slot_or_404(slot_id)
        if request_type not in {t.value for t in RequestType}:
            raise ValidationFailed(f"invalid request_type '{request_type}'")
        if date < _dt.date.today():
            raise ValidationFailed("cannot request an appointment in the past")

        # Duplicate: same student already has an open request on this dated slot.
        for r in self._requests.open_for_student_faculty(student_id, faculty_id):
            rdate, rslot = self._resolve_dated_slot(r)
            if rdate == date and rslot is not None and rslot.id == slot_id:
                raise DuplicateRequest("you already have an open request for this slot")

        # The slot must currently be free (pending requests do NOT occupy it, so
        # two students may still both hold pending requests here).
        if not self._free.is_free(faculty_id=faculty_id, date=date, slot_id=slot_id):
            raise SlotUnavailable("the requested slot is not free on that date")
        slot_minutes = int(
            (
                _dt.datetime.combine(date, slot.end_time)
                - _dt.datetime.combine(date, slot.start_time)
            ).total_seconds() / 60
        )

        if duration_minutes > slot_minutes:
            raise ValidationFailed(
                f"Appointment duration cannot exceed {slot_minutes} minutes"
            )
        req = self._requests.create(
            student_id=student_id, faculty_id=faculty_id,
            request_type=request_type, title=title, description=description,
            status=RequestStatus.PENDING.value,
            scheduled_time=_encode_scheduled(date, slot),
        )
        # Notify faculty (their user id == faculty.id).
        self._notify.notify(
            user_id=faculty_id, event_key="REQUEST_SUBMITTED",
            message=f"{title} — requested for {date} at {slot.slot_name}.",
        )
        return req

    # -- 6/7) approve -------------------------------------------------------
    def approve(self, *, request_id: int, acting_faculty_id: int):
        req = self._requests.by_id(request_id)
        if req is None:
            raise NotFound(f"request {request_id} not found")
        if req.faculty_id != acting_faculty_id:
            raise PermissionDenied("not your request to approve")

        transitions.check_request(RequestStatus(req.status), RequestStatus.APPROVED)
        date, slot = self._resolve_dated_slot(req)
        if date is None or slot is None:
            raise ValidationFailed("request has no resolvable dated slot")
        if not self._free.is_free(faculty_id=req.faculty_id, date=date, slot_id=slot.id):
            raise SlotUnavailable("slot is no longer free; reschedule or reject")

        # queue_entries carries UNIQUE(request_id), so there is at most one row
        # per request for its whole lifetime. A request reaching approval again
        # (after a reschedule) already has a WITHDRAWN entry; we REVIVE that row
        # rather than inserting a duplicate (which would violate uq_queue_request).
        existing = self._queue.by_request(req.id)
        if existing is not None and existing.state not in (
            QueueState.WITHDRAWN.value, QueueState.NO_SHOW.value,
        ):
            # An active entry already exists — approval has effectively happened.
            raise Conflict("request already has an active queue entry")

        # Access token (canonical REQUEST_ACCESS row) for the student user.
        access = self._tokens.issue_request_access(user_id=req.student_id)

        token_number = self._queue.next_token_number(req.faculty_id, date, slot.id)
        pclass = "CONFIRMED"
        view = QueueEntryView(
            id=0, student_id=req.student_id, token_number=token_number,
            priority_class=pclass, state=QueueState.WAITING.value,
            booking_ts=req.created_at, entered_at=req.created_at,
            effective_minutes=0,
        )
        if existing is not None:
            entry = self._queue.revive(
                existing, meeting_date=date, academic_slot_id=slot.id,
                token_number=token_number, access_token_id=access.id,
                priority_class=pclass, priority_score=priority.priority_score(view),
            )
        else:
            entry = self._queue.create(
                request_id=req.id, faculty_id=req.faculty_id, student_id=req.student_id,
                meeting_date=date, academic_slot_id=slot.id, token_number=token_number,
                access_token_id=access.id, priority_class=pclass,
                priority_score=priority.priority_score(view),
                state=QueueState.WAITING.value,
            )
        self._requests.update_status(req, RequestStatus.APPROVED.value)

        self._notify.notify(
            user_id=req.student_id, event_key="REQUEST_APPROVED",
            message=f"Your request '{req.title}' was approved for {date} at {slot.slot_name}.",
        )
        self._notify.notify(
            user_id=req.student_id, event_key="TOKEN_GENERATED",
            message=f"Queue token #{token_number} issued for {date} at {slot.slot_name}.",
        )
        return req, entry

    # -- 8) reject ----------------------------------------------------------
    def reject(self, *, request_id: int, acting_faculty_id: int, reason: str):
        req = self._requests.by_id(request_id)
        if req is None:
            raise NotFound(f"request {request_id} not found")
        if req.faculty_id != acting_faculty_id:
            raise PermissionDenied("not your request to reject")
        transitions.check_request(RequestStatus(req.status), RequestStatus.REJECTED)
        self._requests.update_status(req, RequestStatus.REJECTED.value)
        self._notify.notify(
            user_id=req.student_id, event_key="REQUEST_REJECTED",
            message=f"Your request '{req.title}' was rejected. Reason: {reason}",
        )
        return req

    # -- 9) reschedule ------------------------------------------------------
    def reschedule(self, *, request_id: int, acting_faculty_id: int,
                   date: _dt.date, slot_id: int, note: str | None = None):
        req = self._requests.by_id(request_id)
        if req is None:
            raise NotFound(f"request {request_id} not found")
        if req.faculty_id != acting_faculty_id:
            raise PermissionDenied("not your request to reschedule")
        slot = self._slot_or_404(slot_id)
        transitions.check_request(RequestStatus(req.status), RequestStatus.RESCHEDULED)

        # If it was already approved, withdraw the old queue entry.
        existing = self._queue.by_request(req.id)
        if existing is not None and existing.state in (
            QueueState.WAITING.value, QueueState.CHECKED_IN.value,
            QueueState.READY.value,
        ):
            transitions.check_queue(QueueState(existing.state), QueueState.WITHDRAWN)
            existing.state = QueueState.WITHDRAWN.value

        self._requests.update_status(
            req, RequestStatus.RESCHEDULED.value,
            scheduled_time=_encode_scheduled(date, slot),
        )
        msg = f"Your request '{req.title}' was rescheduled to {date} at {slot.slot_name}."
        if note:
            msg += f" Note: {note}"
        self._notify.notify(user_id=req.student_id, event_key="REQUEST_RESCHEDULED", message=msg)
        return req

    # -- 10) mark busy ------------------------------------------------------
    def mark_busy(self, *, faculty_id: int, acting_faculty_id: int,
                  date: _dt.date, slot_id: int, reason: str | None = None,
                  created_by: int | None = None):
        if faculty_id != acting_faculty_id:
            raise PermissionDenied("faculty can only mark their own slots busy")
        slot = self._slot_or_404(slot_id)

        # Idempotent: a repeat Mark Busy on the same dated slot reuses the
        # existing block rather than tripping uq_faculty_busy. Reconciliation
        # below is naturally idempotent too (already-withdrawn entries are not
        # re-selected, already-rescheduled requests are no longer Pending).
        block, _created = self._busy.get_or_create(
            faculty_id=faculty_id, block_date=date, academic_slot_id=slot_id,
            reason=reason, created_by=created_by or faculty_id,
        )

        # Reconcile affected APPROVED appointments (active queue entries).
        for entry in self._queue.active_on_slot(faculty_id, date, slot_id):
            transitions.check_queue(QueueState(entry.state), QueueState.WITHDRAWN)
            entry.state = QueueState.WITHDRAWN.value
            req = self._requests.by_id(entry.request_id)
            if req is not None and req.status == RequestStatus.APPROVED.value:
                self._requests.update_status(req, RequestStatus.RESCHEDULED.value)
            self._notify.notify(
                user_id=entry.student_id, event_key="FACULTY_BUSY",
                message=(f"The faculty marked {date} at {slot.slot_name} busy; "
                         f"your appointment needs rescheduling."),
            )

        # Reconcile affected PENDING requests on the same dated slot.
        for req in self._requests.pending_for_faculty(faculty_id):
            rdate, rslot = self._resolve_dated_slot(req)
            if rdate == date and rslot is not None and rslot.id == slot_id:
                self._requests.update_status(req, RequestStatus.RESCHEDULED.value)
                self._notify.notify(
                    user_id=req.student_id, event_key="FACULTY_BUSY",
                    message=(f"The faculty marked {date} at {slot.slot_name} busy; "
                             f"please choose another slot."),
                )
        return block

    # -- student cancel -----------------------------------------------------
    def cancel(self, *, request_id: int, acting_student_id: int):
        req = self._requests.by_id(request_id)
        if req is None:
            raise NotFound(f"request {request_id} not found")
        if req.student_id != acting_student_id:
            raise PermissionDenied("not your request to cancel")
        transitions.check_request(RequestStatus(req.status), RequestStatus.CANCELLED)

        existing = self._queue.by_request(req.id)
        if existing is not None and existing.state in (
            QueueState.WAITING.value, QueueState.CHECKED_IN.value, QueueState.READY.value,
        ):
            existing.state = QueueState.WITHDRAWN.value

        self._requests.update_status(req, RequestStatus.CANCELLED.value)
        return req
