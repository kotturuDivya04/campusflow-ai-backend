"""
AdminAccountService — creation of Student and Faculty accounts by an Admin.

This is orchestration only. It introduces NO new table, model or role: it
writes the existing `users` row, the existing `user_roles` link and the
existing `students` / `faculty` subtype row, in that order, using the existing
repositories.

Why that order: in the finalized schema `students.id` and `faculty.id` ARE
`users.id` (shared primary key, FK ON DELETE CASCADE). So the users row must be
flushed first to obtain its generated id, which then becomes the subtype row's
primary key.

Transaction convention (identical to AppointmentService): every repository call
flushes, nothing here commits. The route commits exactly once on success. If
any step raises, no commit happens and `get_db` closes the session, which rolls
the whole transaction back — so a failed role or profile insert can never leave
a half-created user behind.
"""
from __future__ import annotations

from app.core.enums import Role as RoleEnum
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.security import hash_password
from app.models import Faculty, Student
from app.repositories.repositories import (
    AcademicRepository, FacultyRepository, StudentRepository, UserRepository,
)


class AdminAccountService:
    def __init__(
        self,
        *,
        users: UserRepository,
        students: StudentRepository,
        faculty: FacultyRepository,
        academic: AcademicRepository,
    ) -> None:
        self._users = users
        self._students = students
        self._faculty = faculty
        self._academic = academic

    # -- shared helpers -----------------------------------------------------
    def _assert_account_available(self, *, username: str, email: str) -> None:
        if self._users.by_username(username) is not None:
            raise Conflict(f"username '{username}' is already taken")
        if self._users.by_email(email) is not None:
            raise Conflict(f"email '{email}' is already registered")

    def _assert_department(self, department_id: int) -> None:
        if not self._academic.department_exists(department_id):
            raise NotFound(f"department {department_id} not found")

    def _create_user_with_role(self, payload, role: RoleEnum):
        """Create the users row and attach the existing role. Flush only."""
        role_row = self._users.role_by_name(role.value)
        if role_row is None:
            raise NotFound(
                f"role '{role.value}' is not present in the roles table; "
                "the roles seed must be applied before creating accounts")

        user = self._users.create(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
        )
        self._users.assign_role(user.id, role_row.id)
        return user

    # -- 1) add student -----------------------------------------------------
    def create_student(self, payload) -> Student:
        self._assert_account_available(username=payload.username, email=payload.email)
        if self._students.by_roll_number(payload.roll_number) is not None:
            raise Conflict(f"roll_number '{payload.roll_number}' is already in use")
        self._assert_department(payload.department_id)
        if payload.section_id is not None and not self._academic.section_exists(payload.section_id):
            raise NotFound(f"section {payload.section_id} not found")

        user = self._create_user_with_role(payload, RoleEnum.STUDENT)
        return self._students.create(
            id=user.id,
            roll_number=payload.roll_number,
            department_id=payload.department_id,
            section_id=payload.section_id,
            admission_year=payload.admission_year,
            current_semester=payload.current_semester,
        )

    # -- 2) add faculty -----------------------------------------------------
    def create_faculty(self, payload) -> Faculty:
        self._assert_account_available(username=payload.username, email=payload.email)
        if self._faculty.by_code(payload.faculty_code) is not None:
            raise Conflict(f"faculty_code '{payload.faculty_code}' is already in use")
        self._assert_department(payload.department_id)

        user = self._create_user_with_role(payload, RoleEnum.FACULTY)
        return self._faculty.create(
            id=user.id,
            faculty_code=payload.faculty_code,
            department_id=payload.department_id,
            designation=payload.designation,
            office_location=payload.office_location,
        )
