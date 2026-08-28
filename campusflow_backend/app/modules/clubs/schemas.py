"""Clubs module Pydantic schemas."""
from __future__ import annotations

import datetime as _dt

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


class Pagination(BaseModel):
    page: int = 1
    size: int = 25


class ClubBase(BaseModel):
    name: str
    description: str | None = None
    category: str
    mentor_faculty_id: int | None = None


class ClubCreate(ClubBase):
    pass


class ClubUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    mentor_faculty_id: int | None = None


class ClubResponse(BaseModel):
    model_config = ORM
    id: int
    name: str
    description: str | None = None
    category: str
    mentor_faculty_id: int | None = None
    created_at: _dt.datetime | None = None
    updated_at: _dt.datetime | None = None


class ClubListItem(BaseModel):
    model_config = ORM
    id: int
    name: str
    category: str
    mentor_faculty_id: int | None = None


class EventBase(BaseModel):
    title: str
    description: str | None = None
    organizing_club_id: int
    start_time: _dt.datetime
    end_time: _dt.datetime
    status: str | None = None


class EventCreate(EventBase):
    status: str = Field(default="Draft")


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: _dt.datetime | None = None
    end_time: _dt.datetime | None = None
    status: str | None = None


class EventResponse(BaseModel):
    model_config = ORM
    id: int
    title: str
    description: str | None = None
    organizing_club_id: int
    start_time: _dt.datetime
    end_time: _dt.datetime
    status: str
    created_at: _dt.datetime | None = None
    updated_at: _dt.datetime | None = None


class EventListItem(BaseModel):
    model_config = ORM
    id: int
    title: str
    organizing_club_id: int
    start_time: _dt.datetime
    end_time: _dt.datetime
    status: str


class EventQueryParams(BaseModel):
    q: str | None = None
    category: str | None = None
    status: str | None = None
    start_after: _dt.datetime | None = None
    start_before: _dt.datetime | None = None
    page: int = 1
    size: int = 25


class VenueAvailabilityRequest(BaseModel):
    classroom_id: int
    start_time: _dt.datetime
    end_time: _dt.datetime


class VenueBookingCreate(BaseModel):
    event_id: int | None = None
    classroom_id: int
    booked_by_user_id: int
    start_time: _dt.datetime
    end_time: _dt.datetime
    purpose: str
    status: str | None = "Pending"


class VenueBookingUpdate(BaseModel):
    event_id: int | None = None
    classroom_id: int | None = None
    start_time: _dt.datetime | None = None
    end_time: _dt.datetime | None = None
    purpose: str | None = None
    status: str | None = None


class VenueBookingResponse(BaseModel):
    model_config = ORM
    id: int
    event_id: int | None = None
    classroom_id: int
    booked_by_user_id: int
    start_time: _dt.datetime
    end_time: _dt.datetime
    purpose: str
    status: str
    created_at: _dt.datetime | None = None
    updated_at: _dt.datetime | None = None


class RegistrationCreate(BaseModel):
    event_id: int
    student_id: int


class RegistrationResponse(BaseModel):
    model_config = ORM
    id: int
    event_id: int
    student_id: int
    registered_at: _dt.datetime | None = None
    status: str


class RegistrationListItem(BaseModel):
    model_config = ORM
    id: int
    event_id: int
    student_id: int
    registered_at: _dt.datetime | None = None
    status: str


class AttendanceMark(BaseModel):
    event_id: int
    student_id: int
    marked_by_user_id: int
    status: str = Field(default="Present")


class AttendanceBulkItem(BaseModel):
    student_id: int
    status: str = Field(default="Present")


class AttendanceBulkRequest(BaseModel):
    event_id: int
    marked_by_user_id: int
    records: list[AttendanceBulkItem] = Field(default_factory=list)


class AttendanceResponse(BaseModel):
    model_config = ORM
    id: int
    event_id: int
    student_id: int
    marked_by_user_id: int
    marked_at: _dt.datetime | None = None
    status: str


class AnnouncementBase(BaseModel):
    club_id: int
    title: str
    message: str
    target: str = Field(default="ALL_MEMBERS")


class AnnouncementCreate(AnnouncementBase):
    created_by_user_id: int


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    message: str | None = None
    target: str | None = None
    is_published: bool | None = None


class AnnouncementResponse(BaseModel):
    model_config = ORM
    id: int
    club_id: int
    title: str
    message: str
    target: str
    is_published: bool
    published_at: _dt.datetime | None = None
    created_by_user_id: int
    created_at: _dt.datetime | None = None
    updated_at: _dt.datetime | None = None


class AnnouncementListItem(BaseModel):
    model_config = ORM
    id: int
    club_id: int
    title: str
    target: str
    is_published: bool
    published_at: _dt.datetime | None = None
