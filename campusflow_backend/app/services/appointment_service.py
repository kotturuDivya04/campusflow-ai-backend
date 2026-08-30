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

from sqlalchemy import select

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

from app.ai.priority_engine import AIPriorityEngine
from app.models.models import QueueEntry, SwapRequest
from app.ai.models import PriorityDecision
from app.services import queue_logic as _queue_logic

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
        title: str, description: str, request_type: str = RequestType.APPOINTMENT.value,
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
    async def approve(self, *, request_id: int, acting_faculty_id: int):
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

        existing = self._queue.by_request(req.id)
        if existing is not None and existing.state not in (
            QueueState.WITHDRAWN.value, QueueState.NO_SHOW.value,
        ):
            if existing.state == QueueState.WAITING.value and existing.academic_slot_id != slot.id:
                pass
            else:
                raise Conflict("request already has an active queue entry")

        access = self._tokens.issue_request_access(user_id=req.student_id)

        token_number = self._queue.next_token_number(req.faculty_id, date, slot.id)
        pclass = "CONFIRMED"
        view = QueueEntryView(
            id=0, student_id=req.student_id, token_number=token_number,
            priority_class=pclass, state=QueueState.WAITING.value,
            booking_ts=req.created_at, entered_at=req.created_at,
            effective_minutes=0,
        )

        # Call AI Priority Engine (System 1)
        ai_engine = AIPriorityEngine()
        student_data = self._students.by_id(req.student_id)
        try:
            assessment = await ai_engine.calculate_priority(
                appointment_details={"title": req.title, "description": req.description},
                student_details={"id": req.student_id, "name": "Student"},
                faculty_details={"id": req.faculty_id},
                category=pclass,
                reason=req.description or req.title,
                requested_duration=15,
            )
            calc_priority_score = assessment.priority_score
            decision_reason = assessment.decision_reason
            engine_used = "AIPriorityEngine_v1"
        except Exception as e:
            import logging
            logging.error(f"AI Priority Engine failed, falling back to deterministic: {e}")
            # Fallback to deterministic
            calc_priority_score = priority.priority_score(view)
            decision_reason = f"Deterministic fallback due to AI failure: {str(e)}"
            engine_used = "Deterministic_v1"

        if existing is not None:
            entry = self._queue.revive(
                existing, meeting_date=date, academic_slot_id=slot.id,
                token_number=token_number, access_token_id=access.id,
                priority_class=pclass, priority_score=calc_priority_score,
            )
        else:
            entry = self._queue.create(
                request_id=req.id, faculty_id=req.faculty_id, student_id=req.student_id,
                meeting_date=date, academic_slot_id=slot.id, token_number=token_number,
                access_token_id=access.id, priority_class=pclass,
                priority_score=calc_priority_score,
                state=QueueState.WAITING.value,
            )

        self._requests.update_status(req, RequestStatus.APPROVED.value)

        # Persist Priority Decision
        self._requests.db.add(PriorityDecision(
            appointment_id=req.id,
            priority_score=calc_priority_score,
            decision_reason=decision_reason,
            engine_used=engine_used
        ))
        self._requests.db.flush()

        self._notify.notify(
            user_id=req.student_id, event_key="REQUEST_APPROVED",
            message=f"Your request '{req.title}' was approved for {date} at {slot.slot_name}.",
        )
        self._notify.notify(
            user_id=req.student_id, event_key="TOKEN_GENERATED",
            message=f"Queue token #{token_number} issued for {date} at {slot.slot_name}.",
        )

        # HIGH-priority (score >= 70, matching AIPriorityEngine's own
        # HIGH threshold) -> also propose a consent-based swap against
        # whoever currently holds an earlier slot that day, reusing the
        # existing SwapRequest/reevaluate_queue_entry pattern from
        # api/routes/student.py rather than adding a parallel mechanism.
        # This NEVER reorders the queue by itself - only an explicit accept
        # (by the targeted student, via POST /student/swaps/{id}/accept)
        # moves anyone.
        if calc_priority_score >= 70:
            try:
                self._notify.notify(
                    user_id=req.faculty_id, event_key="AI_PRIORITY_FLAGGED",
                    message=(f"AI Priority Engine flagged '{req.title}' as HIGH priority "
                             f"(score {calc_priority_score}). Reason: {decision_reason}"),
                )
                self._notify.notify(
                    user_id=req.student_id, event_key="AI_PRIORITY_FLAGGED",
                    message=(f"Your request '{req.title}' was flagged HIGH priority "
                             f"(score {calc_priority_score}) by the AI Priority Engine."),
                )
                same_session = self._queue.session_entries(req.faculty_id, date)
                pending_target_ids = {
                    row[0] for row in self._requests.db.execute(
                        select(SwapRequest.target_queue_entry_id).where(
                            SwapRequest.status == "PENDING")
                    ).all()
                }
                candidates = [
                    e for e in same_session
                    if e.id != entry.id and e.state == QueueState.WAITING.value
                    and _queue_logic.is_ahead_in_session(
                        e.slot.start_time, e.token_number,
                        slot.start_time, token_number)
                ]
                candidates = _queue_logic.exclude_pending_targets(candidates, pending_target_ids)
                target = _queue_logic.select_next_swap_candidate(
                    candidates, requester_priority_score=calc_priority_score,
                    already_asked_ids=set(),
                )
                if target is not None:
                    swap = SwapRequest(
                        requesting_queue_entry_id=entry.id,
                        target_queue_entry_id=target.id,
                        reason=f"AI Priority Engine: {decision_reason}",
                        status="PENDING",
                    )
                    self._requests.db.add(swap)
                    self._requests.db.flush()
                    self._notify.notify(
                        user_id=target.student_id, event_key="SWAP_REQUESTED",
                        message=(f"Another student's request was flagged urgent by the AI "
                                 f"Priority Engine and would like your earlier slot (token "
                                 f"#{target.token_number}). You may ACCEPT or DECLINE via "
                                 f"POST /student/swaps/{{id}}/accept|decline - swap #{swap.id}."),
                    )
            except Exception:
                import logging
                logging.exception("Auto swap-proposal on HIGH priority approval failed for request_id=%s", req.id)

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
            pass # Keep it WAITING

        new_status = RequestStatus.APPROVED.value if req.status == RequestStatus.APPROVED.value else RequestStatus.RESCHEDULED.value

        self._requests.update_status(
            req, new_status,
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

        block, _created = self._busy.get_or_create(
            faculty_id=faculty_id, block_date=date, academic_slot_id=slot_id,
            reason=reason, created_by=created_by or faculty_id,
        )

        active_entries = self._queue.active_on_slot(faculty_id, date, slot_id)
        # Higher AI-adjusted priority_score gets first pick among students all
        # displaced from the SAME busied period. active_on_slot() has no
        # ORDER BY, so ties (the common case - priority_score defaults to 0
        # unless AI-flagged) must NOT fall back to arbitrary DB row order;
        # order_affected_by_busy() breaks ties by entry.created_at then id,
        # consistent with the FCFS tiebreak convention used everywhere else.
        affected = _queue_logic.order_affected_by_busy(active_entries)

        import datetime as _dt_native
        now = _dt_native.datetime.utcnow()

        # ROOT-CAUSE FIX of the prior cascade attempt: it computed free_slots
        # ONCE before the loop and .pop(0)'d from that single stale list -
        # which (a) never accounted for a period's real remaining 15-min
        # capacity (a period could absorb 2-3 students, not just one "pop"),
        # (b) could move a student BACKWARD in time to an earlier period that
        # day, and (c) never looked at subsequent days when today was full.
        # Now: for each affected student, freshly RE-QUERY capacity-aware free
        # slots (via the just-fixed FreeSlotService, which reflects every
        # previous reassignment already flushed this loop) at/after the
        # vacated slot's start time, then subsequent days, same as the
        # is-genuinely-full-vs-not fix applied to the core scheduling bug.
        for entry in affected:
            entry.reschedule_started_at = now
            req = self._requests.by_id(entry.request_id)

            transitions.check_queue(QueueState(entry.state), QueueState.WITHDRAWN)
            entry.state = QueueState.WITHDRAWN.value
            self._queue.flush()

            replacement = self._find_replacement_slot(
                faculty_id=faculty_id, start_date=date,
                not_before_min=slot.start_min(), exclude_slot_id=slot_id,
            )

            if replacement is not None:
                rdate, rslot = replacement
                self._reassign_to_slot(request=req, entry=entry, date=rdate, slot=rslot)
                entry.reschedule_completed_at = now
                self._notify.notify(
                    user_id=entry.student_id, event_key="FACULTY_BUSY",
                    message=(f"Faculty marked {slot.slot_name} busy. Your appointment was "
                             f"automatically rebooked to {rdate} at {rslot.slot_name} "
                             f"(token #{entry.token_number}).")
                )
            else:
                entry.reschedule_completed_at = now
                if req and req.status == RequestStatus.APPROVED.value:
                    self._requests.update_status(req, RequestStatus.RESCHEDULED.value)
                self._notify.notify(
                    user_id=entry.student_id, event_key="FACULTY_BUSY",
                    message=(f"Faculty marked {slot.slot_name} busy. No replacement slot was found "
                             f"within the next {self._REPLACEMENT_SEARCH_DAYS} days. Please submit a "
                             f"new request for a slot that works for you - you have NOT been "
                             f"silently dropped.")
                )

        # Reconcile affected PENDING requests on the same dated slot.
        for req in self._requests.pending_for_faculty(faculty_id):
            rdate, rslot = self._resolve_dated_slot(req)
            if rdate == date and rslot is not None and rslot.id == slot_id:
                self._requests.update_status(req, RequestStatus.RESCHEDULED.value)
                self._notify.notify(
                    user_id=req.student_id, event_key="FACULTY_BUSY",
                    message=(f"The faculty marked {date} at {slot.slot_name} busy; "
                             f"please choose another slot.")
                )
        return block

    # -- 10b) mark unavailable (whole day) -----------------------------------
    def mark_unavailable_day(self, *, faculty_id: int, acting_faculty_id: int,
                             date: _dt.date, reason: str | None = None,
                             created_by: int | None = None):
        """
        Faculty UNAVAILABLE for the whole day, distinct from a single-slot
        BUSY. Modeled as "busy for every academic_slot that day" - reuses
        mark_busy's own (now capacity-aware, multi-day) cascade reschedule
        for every slot, consistent with the existing per-slot
        faculty_busy_blocks design rather than inventing a new faculty-status
        column.
        """
        if faculty_id != acting_faculty_id:
            raise PermissionDenied("faculty can only mark their own day unavailable")

        full_reason = "UNAVAILABLE (whole day)" + (f": {reason}" if reason else "")
        blocks = []
        affected_student_ids: set[int] = set()
        for slot in self._slots.as_views():
            for entry in self._queue.active_on_slot(faculty_id, date, slot.id):
                affected_student_ids.add(entry.student_id)
            block = self.mark_busy(
                faculty_id=faculty_id, acting_faculty_id=acting_faculty_id,
                date=date, slot_id=slot.id, reason=full_reason,
                created_by=created_by or faculty_id,
            )
            blocks.append(block)

        for student_id in affected_student_ids:
            self._notify.notify(
                user_id=student_id, event_key="FACULTY_UNAVAILABLE",
                message=(f"Faculty {faculty_id} is unavailable for the entire day of {date}. "
                         f"Any appointment you had that day was reconciled - check your "
                         f"notifications for whether you were rebooked or need to re-request."),
            )
        self._notify.notify(
            user_id=faculty_id, event_key="FACULTY_UNAVAILABLE",
            message=(f"You marked {date} fully unavailable. {len(blocks)} slot(s) blocked; "
                     f"{len(affected_student_ids)} student(s) affected and notified."),
        )
        return blocks

    # -- BUSY cascade-reschedule helpers -------------------------------------
    _REPLACEMENT_SEARCH_DAYS = 14

    def _find_replacement_slot(self, *, faculty_id: int, start_date: _dt.date,
                               not_before_min: int, exclude_slot_id: int | None):
        """
        Search start_date (at/after not_before_min, excluding the vacated
        slot) then each of the following _REPLACEMENT_SEARCH_DAYS days for
        the earliest slot the capacity-aware FreeSlotService still reports as
        free. Returns (date, SlotView) or None if the horizon is exhausted -
        callers must not fabricate a slot in that case.
        """
        from app.services.free_slot_engine import first_valid_replacement

        for offset in range(0, self._REPLACEMENT_SEARCH_DAYS + 1):
            day = start_date + _dt.timedelta(days=offset)
            free_today = self._free.compute(faculty_id=faculty_id, date=day)
            bound = not_before_min if offset == 0 else 0
            excl = exclude_slot_id if offset == 0 else None
            replacement = first_valid_replacement(
                free_slots=free_today, not_before_min=bound, exclude_slot_id=excl)
            if replacement is not None:
                return day, replacement
        return None

    def _reassign_to_slot(self, *, request, entry, date: _dt.date, slot: SlotView):
        """
        Revive a WITHDRAWN queue entry into a newly found replacement slot and
        put its request back to Approved. Preserves the request's original
        created_at (never touched) so FIFO/audit history stays intact.
        """
        new_token = self._queue.next_token_number(entry.faculty_id, date, slot.id)
        self._queue.revive(
            entry, meeting_date=date, academic_slot_id=slot.id,
            token_number=new_token, access_token_id=entry.access_token_id,
            priority_class=entry.priority_class, priority_score=entry.priority_score,
        )
        if request is not None:
            self._requests.update_status(
                request, RequestStatus.APPROVED.value,
                scheduled_time=_encode_scheduled(date, slot),
            )
        return entry

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
