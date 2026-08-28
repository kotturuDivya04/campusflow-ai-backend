"""Clubs module API router."""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext,
    get_current_user,
    get_db,
    get_notification_service,
)
from app.notifications.service import NotificationService
from app.modules.clubs.service import ClubService
from app.modules.clubs.repository import (
    AnnouncementRepository,
    ClubRepository,
    EventAttendanceRepository,
    EventRegistrationRepository,
    EventRepository,
    VenueBookingRepository,
)
from app.modules.clubs.permissions import (
    require_announcement_manager,
    require_attendance_manager,
    require_club_coordinator,
    require_event_manager,
    require_registration_user,
)
from app.modules.clubs.schemas import (
    AnnouncementCreate,
    AnnouncementResponse,
    AnnouncementUpdate,
    AttendanceBulkRequest,
    AttendanceResponse,
    AttendanceMark,
    ClubCreate,
    ClubListItem,
    ClubResponse,
    ClubUpdate,
    EventCreate,
    EventListItem,
    EventResponse,
    EventUpdate,
    RegistrationCreate,
    RegistrationListItem,
    RegistrationResponse,
    VenueBookingCreate,
    VenueBookingResponse,
    VenueBookingUpdate,
)
from app.repositories.repositories import TimetableRepository

router = APIRouter(prefix="", tags=["clubs"])


def get_club_service(db: Session = Depends(get_db), notifications: NotificationService = Depends(get_notification_service)) -> ClubService:
    return ClubService(
        club_repo=ClubRepository(db),
        event_repo=EventRepository(db),
        booking_repo=VenueBookingRepository(db),
        registration_repo=EventRegistrationRepository(db),
        attendance_repo=EventAttendanceRepository(db),
        announcement_repo=AnnouncementRepository(db),
        timetable_repo=TimetableRepository(db),
        notifications=notifications,
    )


@router.post("/clubs", response_model=ClubResponse)
def create_club(payload: ClubCreate,
                auth: AuthContext = Depends(require_club_coordinator),
                service: ClubService = Depends(get_club_service)):
    club = service.create_club(payload.model_dump())
    service._notifications.notify(
        user_id=auth.user_id,
        event_key="SYSTEM",
        message=f"Club '{club.name}' created by user {auth.user_id}",
    )
    return club


@router.get("/clubs", response_model=list[ClubListItem])
def list_clubs(page: int = Query(1, ge=1), size: int = Query(25, ge=1),
               auth: AuthContext = Depends(get_current_user),
               service: ClubService = Depends(get_club_service)):
    return service.list_clubs(page=page, size=size)


@router.get("/clubs/{club_id}", response_model=ClubResponse)
def get_club(club_id: int,
             auth: AuthContext = Depends(get_current_user),
             service: ClubService = Depends(get_club_service)):
    return service.get_club(club_id)


@router.put("/clubs/{club_id}", response_model=ClubResponse)
def update_club(club_id: int, payload: ClubUpdate,
                auth: AuthContext = Depends(require_club_coordinator),
                service: ClubService = Depends(get_club_service)):
    return service.update_club(club_id, payload.model_dump(exclude_none=True))


@router.delete("/clubs/{club_id}")
def delete_club(club_id: int,
                auth: AuthContext = Depends(require_club_coordinator),
                service: ClubService = Depends(get_club_service)):
    service.delete_club(club_id)
    return {"detail": "club deleted"}


# --- events ---------------------------------------------------------------
@router.post("/events", response_model=EventResponse)
def create_event(payload: EventCreate,
                 auth: AuthContext = Depends(require_event_manager),
                 service: ClubService = Depends(get_club_service)):
    return service.create_event(payload.model_dump())


@router.get("/events", response_model=list[EventListItem])
def list_events(q: str | None = None,
                status: str | None = None,
                page: int = Query(1, ge=1),
                size: int = Query(25, ge=1),
                auth: AuthContext = Depends(get_current_user),
                service: ClubService = Depends(get_club_service)):
    return service.search_events(q=q, status=status, page=page, size=size)

@router.get("/events/upcoming", response_model=list[EventListItem])
def upcoming_events(page: int = Query(1, ge=1), size: int = Query(25, ge=1),
                    auth: AuthContext = Depends(get_current_user),
                    service: ClubService = Depends(get_club_service)):
    return service.list_upcoming_events(page=page, size=size)


@router.get("/events/past", response_model=list[EventListItem])
def past_events(page: int = Query(1, ge=1), size: int = Query(25, ge=1),
                auth: AuthContext = Depends(get_current_user),
                service: ClubService = Depends(get_club_service)):
    return service.list_past_events(page=page, size=size)

@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int,
              auth: AuthContext = Depends(get_current_user),
              service: ClubService = Depends(get_club_service)):
    return service.get_event(event_id)


@router.put("/events/{event_id}", response_model=EventResponse)
def update_event(event_id: int, payload: EventUpdate,
                 auth: AuthContext = Depends(require_event_manager),
                 service: ClubService = Depends(get_club_service)):
    return service.update_event(event_id, payload.model_dump(exclude_none=True))


@router.delete("/events/{event_id}")
def delete_event(event_id: int,
                 auth: AuthContext = Depends(require_event_manager),
                 service: ClubService = Depends(get_club_service)):
    service.delete_event(event_id)
    return {"detail": "event deleted"}

# --- venues ---------------------------------------------------------------
@router.get("/venues/availability")
def check_venue_availability(
    classroom_id: int,
    start_time: _dt.datetime,
    end_time: _dt.datetime,
    auth: AuthContext = Depends(get_current_user),
    service: ClubService = Depends(get_club_service),
):
    available = service._venue_manager.check_availability(
        classroom_id=classroom_id,
        start_time=start_time,
        end_time=end_time,
    )
    return {"available": available}


@router.post("/venues/book", response_model=VenueBookingResponse)
def book_venue(payload: VenueBookingCreate,
               auth: AuthContext = Depends(require_event_manager),
               service: ClubService = Depends(get_club_service)):
    return service._venue_manager.create_booking(payload.model_dump())


@router.put("/venues/book/{booking_id}", response_model=VenueBookingResponse)
def update_venue_booking(booking_id: int, payload: VenueBookingUpdate,
                         auth: AuthContext = Depends(require_event_manager),
                         service: ClubService = Depends(get_club_service)):
    return service._venue_manager.update_booking(booking_id, payload.model_dump(exclude_none=True))


@router.delete("/venues/book/{booking_id}")
def cancel_venue_booking(booking_id: int,
                         auth: AuthContext = Depends(require_event_manager),
                         service: ClubService = Depends(get_club_service)):
    service._venue_manager.cancel_booking(booking_id)
    return {"detail": "booking cancelled"}


# --- registrations --------------------------------------------------------
@router.post("/registrations", response_model=RegistrationResponse)
def register_student(payload: RegistrationCreate,
                     auth: AuthContext = Depends(require_registration_user),
                     service: ClubService = Depends(get_club_service)):
    return service.register_student(payload.event_id, auth.user_id)


@router.delete("/registrations/{registration_id}")
def cancel_registration(registration_id: int,
                        auth: AuthContext = Depends(require_registration_user),
                        service: ClubService = Depends(get_club_service)):
    service.cancel_registration(registration_id, auth.user_id)
    return {"detail": "registration cancelled"}


@router.get("/registrations/event/{event_id}", response_model=list[RegistrationListItem])
def registrations_for_event(event_id: int,
                            auth: AuthContext = Depends(require_event_manager),
                            service: ClubService = Depends(get_club_service)):
    return service.registrations_for_event(event_id)


@router.get("/registrations/student/{student_id}", response_model=list[RegistrationListItem])
def registrations_for_student(student_id: int,
                              auth: AuthContext = Depends(require_registration_user),
                              service: ClubService = Depends(get_club_service)):
    return service.registrations_for_student(student_id)


# --- attendance -----------------------------------------------------------
@router.post("/attendance", response_model=AttendanceResponse)
def mark_attendance(payload: AttendanceMark,
                    auth: AuthContext = Depends(require_attendance_manager),
                    service: ClubService = Depends(get_club_service)):
    payload_data = payload.model_dump(exclude_none=True)
    payload_data["marked_by_user_id"] = auth.user_id
    return service.mark_attendance(payload_data)


@router.post("/attendance/bulk", response_model=list[AttendanceResponse])
def bulk_attendance(payload: AttendanceBulkRequest,
                    auth: AuthContext = Depends(require_attendance_manager),
                    service: ClubService = Depends(get_club_service)):
    payload_data = payload.model_dump(exclude_none=True)
    payload_data["marked_by_user_id"] = auth.user_id
    return service.bulk_attendance(payload_data)


@router.get("/attendance/event/{event_id}", response_model=list[AttendanceResponse])
def attendance_for_event(event_id: int,
                         auth: AuthContext = Depends(require_attendance_manager),
                         service: ClubService = Depends(get_club_service)):
    return service.attendance_for_event(event_id)


@router.get("/attendance/student/{student_id}", response_model=list[AttendanceResponse])
def attendance_for_student(student_id: int,
                            auth: AuthContext = Depends(require_registration_user),
                            service: ClubService = Depends(get_club_service)):
    return service.attendance_for_student(student_id)


# --- announcements --------------------------------------------------------
@router.post("/announcements", response_model=AnnouncementResponse)
def create_announcement(payload: AnnouncementCreate,
                        auth: AuthContext = Depends(require_announcement_manager),
                        service: ClubService = Depends(get_club_service)):
    payload_data = payload.model_dump(exclude_none=True)
    payload_data["created_by_user_id"] = auth.user_id
    return service.create_announcement(payload_data)


@router.get("/announcements", response_model=list[AnnouncementResponse])
def list_announcements(page: int = Query(1, ge=1), size: int = Query(25, ge=1),
                       auth: AuthContext = Depends(get_current_user),
                       service: ClubService = Depends(get_club_service)):
    return service.list_announcements(page=page, size=size)


@router.put("/announcements/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(announcement_id: int, payload: AnnouncementUpdate,
                        auth: AuthContext = Depends(require_announcement_manager),
                        service: ClubService = Depends(get_club_service)):
    return service.update_announcement(announcement_id, payload.model_dump(exclude_none=True))


@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: int,
                        auth: AuthContext = Depends(require_announcement_manager),
                        service: ClubService = Depends(get_club_service)):
    service.delete_announcement(announcement_id)
    return {"detail": "announcement deleted"}
