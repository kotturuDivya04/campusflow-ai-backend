"""
Faculty routes. Thin: they validate identity/ownership and delegate to services.
"""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext, get_appointment_service, get_current_user,
    get_free_slot_service, get_queue_service, require_faculty,
)
from app.core.errors import NotFound, PermissionDenied
from app.db.session import get_db
from app.repositories.repositories import (
    FacultyRepository, SlotRepository, TimetableRepository,
)
from app.schemas import (
    BusyPayload, FacultyProfile, FreeSlotOut, LiveQueueOut, LiveQueueSlot,
    Message, QueueEntryOut, RejectPayload, RequestOut, ReschedulePayload,
    TimetableRow,
)
from app.services.appointment_service import AppointmentService
from app.services.free_slot_service import FreeSlotService
from app.services.queue_service import QueueService

router = APIRouter(prefix="/faculty", tags=["faculty"])


def _self_or_403(auth: AuthContext, faculty_id: int) -> None:
    if auth.user_id != faculty_id:
        raise PermissionDenied("faculty may only act on their own records")


# --- profile & timetable ----------------------------------------------------
@router.get("/me", response_model=FacultyProfile)
def my_profile(auth: AuthContext = Depends(require_faculty),
               db: Session = Depends(get_db)):
    fac = FacultyRepository(db).by_id(auth.user_id)
    if fac is None:
        raise NotFound("faculty profile not found")
    return FacultyProfile(
        id=fac.id, faculty_code=fac.faculty_code, department_id=fac.department_id,
        designation=fac.designation, office_location=fac.office_location,
        first_name=fac.user.first_name, last_name=fac.user.last_name,
        email=fac.user.email,
    )


@router.get("/me/timetable", response_model=list[TimetableRow])
def my_timetable(auth: AuthContext = Depends(require_faculty),
                 db: Session = Depends(get_db)):
    return TimetableRepository(db).for_faculty(auth.user_id)


# --- free slots (public to authenticated users; students need this too) -----
@router.get("/{faculty_id}/free-slots", response_model=list[FreeSlotOut])
def free_slots(
    faculty_id: int,
    date: _dt.date = Query(..., description="YYYY-MM-DD"),
    auth: AuthContext = Depends(get_current_user),
    service: FreeSlotService = Depends(get_free_slot_service),
):
    slots = service.compute(faculty_id=faculty_id, date=date)
    return [
        FreeSlotOut(slot_id=s.id, slot_name=s.slot_name, start_time=s.start_time,
                    end_time=s.end_time, date=date)
        for s in slots
    ]


# --- request decisions ------------------------------------------------------
@router.get("/me/requests/pending", response_model=list[RequestOut])
def pending_requests(auth: AuthContext = Depends(require_faculty),
                     db: Session = Depends(get_db)):
    from app.repositories.repositories import RequestRepository
    return RequestRepository(db).pending_for_faculty(auth.user_id)


@router.post("/requests/{request_id}/approve", response_model=RequestOut)
def approve(request_id: int,
            auth: AuthContext = Depends(require_faculty),
            db: Session = Depends(get_db),
            service: AppointmentService = Depends(get_appointment_service)):
    req, _entry = service.approve(request_id=request_id, acting_faculty_id=auth.user_id)
    db.commit()
    return req


@router.post("/requests/{request_id}/reject", response_model=RequestOut)
def reject(request_id: int, payload: RejectPayload,
           auth: AuthContext = Depends(require_faculty),
           db: Session = Depends(get_db),
           service: AppointmentService = Depends(get_appointment_service)):
    req = service.reject(request_id=request_id, acting_faculty_id=auth.user_id,
                         reason=payload.reason)
    db.commit()
    return req


@router.post("/requests/{request_id}/reschedule", response_model=RequestOut)
def reschedule(request_id: int, payload: ReschedulePayload,
               auth: AuthContext = Depends(require_faculty),
               db: Session = Depends(get_db),
               service: AppointmentService = Depends(get_appointment_service)):
    req = service.reschedule(
        request_id=request_id, acting_faculty_id=auth.user_id,
        date=payload.date, slot_id=payload.academic_slot_id, note=payload.note)
    db.commit()
    return req


@router.post("/me/busy", response_model=Message)
def mark_busy(payload: BusyPayload,
              auth: AuthContext = Depends(require_faculty),
              db: Session = Depends(get_db),
              service: AppointmentService = Depends(get_appointment_service)):
    service.mark_busy(
        faculty_id=auth.user_id, acting_faculty_id=auth.user_id,
        date=payload.date, slot_id=payload.academic_slot_id,
        reason=payload.reason, created_by=auth.user_id)
    db.commit()
    return Message(detail="slot marked busy; affected appointments were reconciled")


# --- live queue & meetings --------------------------------------------------
@router.get("/me/queue", response_model=LiveQueueOut)
def live_queue(date: _dt.date = Query(...),
               auth: AuthContext = Depends(require_faculty),
               service: QueueService = Depends(get_queue_service)):
    groups = service.live_queue(faculty_id=auth.user_id, date=date)
    return LiveQueueOut(
        faculty_id=auth.user_id, meeting_date=date,
        slots=[
            LiveQueueSlot(
                faculty_id=g["faculty_id"], meeting_date=g["meeting_date"],
                academic_slot_id=g["academic_slot_id"],
                current_token=g["current_token"],
                waiting_tokens=g["waiting_tokens"],
                completed_tokens=g["completed_tokens"],
                delayed_tokens=g["delayed_tokens"],
                entries=[QueueEntryOut.model_validate(e) for e in g["entries"]],
            ) for g in groups
        ],
    )


@router.post("/queue/{entry_id}/begin", response_model=QueueEntryOut)
def begin_meeting(entry_id: int,
                  auth: AuthContext = Depends(require_faculty),
                  db: Session = Depends(get_db),
                  service: QueueService = Depends(get_queue_service)):
    entry = service.begin_meeting(entry_id=entry_id, acting_faculty_id=auth.user_id)
    db.commit()
    return entry


@router.post("/queue/{entry_id}/complete", response_model=QueueEntryOut)
def complete_meeting(entry_id: int,
                     auth: AuthContext = Depends(require_faculty),
                     db: Session = Depends(get_db),
                     service: QueueService = Depends(get_queue_service)):
    entry = service.complete_meeting(entry_id=entry_id, acting_faculty_id=auth.user_id)
    db.commit()
    return entry


@router.post("/queue/{entry_id}/no-show", response_model=QueueEntryOut)
def no_show(entry_id: int,
            auth: AuthContext = Depends(require_faculty),
            db: Session = Depends(get_db),
            service: QueueService = Depends(get_queue_service)):
    entry = service.mark_no_show(entry_id=entry_id, acting_faculty_id=auth.user_id)
    db.commit()
    return entry


# --- AI assistant (advisory, deterministic) ---------------------------------
@router.get("/me/schedule-summary", response_model=Message)
def schedule_summary(date: _dt.date = Query(...),
                     auth: AuthContext = Depends(require_faculty),
                     db: Session = Depends(get_db),
                     free: FreeSlotService = Depends(get_free_slot_service)):
    from app.ai.deterministic import DeterministicScheduleSummarizer
    from app.services.free_slot_service import weekday_name

    slots = {s.id: s for s in SlotRepository(db).as_views()}
    year, semester = free._current_term()  # documented internal reuse
    teaching_ids = TimetableRepository(db).teaching_slot_ids(
        auth.user_id, weekday_name(date), year, semester)
    free_slots_ = free.compute(faculty_id=auth.user_id, date=date)
    from app.repositories.repositories import RequestRepository
    appt_ids = RequestRepository(db).approved_slot_ids_on_date(auth.user_id, date)

    text = DeterministicScheduleSummarizer().summarize(
        date=date,
        teaching=[slots[i] for i in teaching_ids if i in slots],
        appointments=[slots[i] for i in appt_ids if i in slots],
        free=free_slots_,
    )
    return Message(detail=text)
