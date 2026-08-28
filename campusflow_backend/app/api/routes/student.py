"""
Student routes. Thin: identity/ownership checks then delegate to services.
"""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext, get_appointment_service, get_current_user,
    get_free_slot_service, get_queue_service, require_student,
)
from app.core.errors import NotFound, PermissionDenied
from app.db.session import get_db
from app.repositories.repositories import (
    FacultyRepository, NotificationRepository, RequestRepository,
    StudentRepository,
)
from app.schemas import (
    AppointmentCreate, DelayPayload, ExchangePayload, FacultyProfile,
    Message, NotificationOut, QueueEntryOut, RequestOut, SlotRecommendation,
    StudentProfile, TokenView,
)
from app.services.appointment_service import AppointmentService
from app.services.free_slot_service import FreeSlotService
from app.services.queue_service import QueueService

router = APIRouter(prefix="/student", tags=["student"])


@router.get("/me", response_model=StudentProfile)
def my_profile(auth: AuthContext = Depends(require_student),
               db: Session = Depends(get_db)):
    st = StudentRepository(db).by_id(auth.user_id)
    if st is None:
        raise NotFound("student profile not found")
    return StudentProfile(
        id=st.id, roll_number=st.roll_number, department_id=st.department_id,
        section_id=st.section_id, admission_year=st.admission_year,
        current_semester=st.current_semester,
        first_name=st.user.first_name, last_name=st.user.last_name,
        email=st.user.email,
    )


@router.get("/faculty", response_model=list[FacultyProfile])
def search_faculty(q: str | None = Query(default=None, description="name or code"),
                   auth: AuthContext = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    rows = FacultyRepository(db).search(q)
    return [
        FacultyProfile(
            id=f.id, faculty_code=f.faculty_code, department_id=f.department_id,
            designation=f.designation, office_location=f.office_location,
            first_name=f.user.first_name, last_name=f.user.last_name,
            email=f.user.email,
        ) for f in rows
    ]


# --- appointments -----------------------------------------------------------
@router.post("/appointments", response_model=RequestOut, status_code=201)
def submit_appointment(payload: AppointmentCreate,
                       auth: AuthContext = Depends(require_student),
                       db: Session = Depends(get_db),
                       service: AppointmentService = Depends(get_appointment_service)):
    req = service.submit(
        student_id=auth.user_id, faculty_id=payload.faculty_id,
        date=payload.date, slot_id=payload.academic_slot_id,
        title=payload.title, description=payload.description,
        request_type=payload.request_type,
        duration_minutes=payload.duration_minutes,
    )
    db.commit()
    return req


@router.get("/appointments", response_model=list[RequestOut])
def my_requests(auth: AuthContext = Depends(require_student),
                db: Session = Depends(get_db)):
    return RequestRepository(db).for_student(auth.user_id)


@router.post("/appointments/{request_id}/cancel", response_model=RequestOut)
def cancel(request_id: int,
           auth: AuthContext = Depends(require_student),
           db: Session = Depends(get_db),
           service: AppointmentService = Depends(get_appointment_service)):
    req = service.cancel(request_id=request_id, acting_student_id=auth.user_id)
    db.commit()
    return req


# --- queue ------------------------------------------------------------------
@router.get("/tokens", response_model=list[QueueEntryOut])
def my_tokens(auth: AuthContext = Depends(require_student),
              db: Session = Depends(get_db)):
    from app.repositories.repositories import QueueRepository
    return QueueRepository(db).for_student(auth.user_id)


@router.get("/tokens/{entry_id}", response_model=TokenView)
def token_with_eta(entry_id: int,
                   auth: AuthContext = Depends(require_student),
                   service: QueueService = Depends(get_queue_service)):
    return TokenView(**service.token_view(entry_id=entry_id,
                                          acting_student_id=auth.user_id))


@router.post("/tokens/{entry_id}/check-in", response_model=QueueEntryOut)
def check_in(entry_id: int,
             auth: AuthContext = Depends(require_student),
             db: Session = Depends(get_db),
             service: QueueService = Depends(get_queue_service)):
    entry = service.check_in(entry_id=entry_id, acting_student_id=auth.user_id)
    db.commit()
    return entry


@router.post("/tokens/{entry_id}/delay", response_model=QueueEntryOut)
def report_delay(entry_id: int, payload: DelayPayload,
                 auth: AuthContext = Depends(require_student),
                 db: Session = Depends(get_db),
                 service: QueueService = Depends(get_queue_service)):
    entry = service.report_delay(entry_id=entry_id, acting_student_id=auth.user_id,
                                 minutes=payload.minutes)
    db.commit()
    return entry


@router.post("/tokens/{entry_id}/exchange", response_model=list[QueueEntryOut])
def exchange(entry_id: int, payload: ExchangePayload,
             auth: AuthContext = Depends(require_student),
             db: Session = Depends(get_db),
             service: QueueService = Depends(get_queue_service)):
    a, b = service.exchange(entry_id=entry_id,
                            other_entry_id=payload.other_queue_entry_id,
                            acting_student_id=auth.user_id)
    db.commit()
    return [a, b]


# --- notifications ----------------------------------------------------------
@router.get("/notifications", response_model=list[NotificationOut])
def notifications(auth: AuthContext = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return NotificationRepository(db).for_user(auth.user_id)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(notification_id: int,
                          auth: AuthContext = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    repo = NotificationRepository(db)
    n = repo.by_id(notification_id)
    if n is None:
        raise NotFound("notification not found")
    if n.user_id != auth.user_id:
        raise PermissionDenied("not your notification")
    n = repo.mark_read(n)
    db.commit()
    return n


@router.post("/notifications/read-all", response_model=Message)
def mark_all_notifications_read(auth: AuthContext = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    count = NotificationRepository(db).mark_all_read(auth.user_id)
    db.commit()
    return Message(detail=f"marked {count} notification(s) as read")


# --- AI assistant (advisory) ------------------------------------------------
@router.get("/faculty/{faculty_id}/recommended-slots",
            response_model=list[SlotRecommendation])
def recommended_slots(faculty_id: int, date: _dt.date = Query(...),
                      auth: AuthContext = Depends(get_current_user),
                      free: FreeSlotService = Depends(get_free_slot_service)):
    from app.ai.deterministic import DeterministicSlotRecommender

    slots = free.compute(faculty_id=faculty_id, date=date)
    return [
        SlotRecommendation(**r)
        for r in DeterministicSlotRecommender().recommend(free_slots=slots, date=date)
    ]
