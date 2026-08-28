"""
Timetable importer.

Structure (brief: "Keep parsing logic separate from persistence logic"):

    parse_csv / parse_json  -> pure functions, stdlib only, return ParsedRows
    TimetableImporter       -> resolves human-readable references to primary
                               keys, validates, and persists

Expected columns (matching database/sample_data/timetable.csv):
    section_name, subject_code, faculty_code, classroom_number,
    slot_name, day_of_week, academic_year, semester

Malformed rows are rejected with a reason and never abort the whole import; the
result is an ImportSummary of inserted / skipped (duplicates) / failed + errors.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

from app.core.enums import DAYS_OF_WEEK

REQUIRED_COLUMNS = (
    "section_name", "subject_code", "faculty_code", "classroom_number",
    "slot_name", "day_of_week", "academic_year", "semester",
)


@dataclass
class ParsedRow:
    line_no: int
    data: dict
    error: str | None = None


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    fatal: str | None = None


# ---------------------------------------------------------------------------
# PURE PARSING (no database involvement)
# ---------------------------------------------------------------------------
def _validate_row(line_no: int, raw: dict) -> ParsedRow:
    data = {k: (str(v).strip() if v is not None else "") for k, v in raw.items()}
    missing = [c for c in REQUIRED_COLUMNS if not data.get(c)]
    if missing:
        return ParsedRow(line_no, data, f"missing value(s): {', '.join(missing)}")
    if data["day_of_week"] not in DAYS_OF_WEEK:
        return ParsedRow(line_no, data, f"invalid day_of_week '{data['day_of_week']}'")
    try:
        data["academic_year"] = int(data["academic_year"])
    except ValueError:
        return ParsedRow(line_no, data, f"academic_year must be an integer")
    return ParsedRow(line_no, data)


def parse_csv(text: str) -> ParseResult:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return ParseResult(fatal="file is empty or has no header row")
    header = [h.strip() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        return ParseResult(fatal=f"missing required column(s): {', '.join(missing)}")
    rows = [_validate_row(i, r) for i, r in enumerate(reader, start=2)]
    return ParseResult(rows=rows)


def parse_json(text: str) -> ParseResult:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return ParseResult(fatal=f"invalid JSON: {exc.msg}")
    if not isinstance(payload, list):
        return ParseResult(fatal="JSON payload must be a list of row objects")
    rows = []
    for i, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            rows.append(ParsedRow(i, {}, "row is not an object"))
            continue
        rows.append(_validate_row(i, item))
    return ParseResult(rows=rows)


# ---------------------------------------------------------------------------
# PERSISTENCE
# ---------------------------------------------------------------------------
class TimetableImporter:
    """Resolves references to ids and writes timetable rows."""

    def __init__(self, db) -> None:
        self.db = db

    def _lookup_maps(self) -> dict:
        from sqlalchemy import select

        from app.models import (
            AcademicSlot, Classroom, Faculty, Section, Subject,
        )
        return {
            "section": {r.name: r.id for r in self.db.scalars(select(Section))},
            "subject": {r.code: r.id for r in self.db.scalars(select(Subject))},
            "faculty": {r.faculty_code: r.id for r in self.db.scalars(select(Faculty))},
            "classroom": {r.room_number: r.id for r in self.db.scalars(select(Classroom))},
            "slot": {r.slot_name: r.id for r in self.db.scalars(select(AcademicSlot))},
        }

    def import_rows(self, parsed: ParseResult) -> dict:
        from app.repositories.repositories import TimetableRepository

        if parsed.fatal:
            return {"inserted": 0, "skipped": 0, "failed": 0, "errors": [parsed.fatal]}

        maps = self._lookup_maps()
        repo = TimetableRepository(self.db)
        inserted = skipped = failed = 0
        errors: list[str] = []

        for row in parsed.rows:
            if row.error:
                failed += 1
                errors.append(f"row {row.line_no}: {row.error}")
                continue
            d = row.data
            ids = {
                "section_id": maps["section"].get(d["section_name"]),
                "subject_id": maps["subject"].get(d["subject_code"]),
                "faculty_id": maps["faculty"].get(d["faculty_code"]),
                "classroom_id": maps["classroom"].get(d["classroom_number"]),
                "academic_slot_id": maps["slot"].get(d["slot_name"]),
            }
            unresolved = [k for k, v in ids.items() if v is None]
            if unresolved:
                failed += 1
                errors.append(
                    f"row {row.line_no}: unknown reference for {', '.join(unresolved)}")
                continue

            payload = dict(
                ids,
                day_of_week=d["day_of_week"],
                academic_year=d["academic_year"],
                semester=d["semester"],
            )
            if repo.exists(**payload):
                skipped += 1
                continue
            try:
                repo.add(**payload)
                inserted += 1
            except Exception as exc:  # unique constraint / FK violation
                self.db.rollback()
                failed += 1
                errors.append(f"row {row.line_no}: {type(exc).__name__}")

        return {"inserted": inserted, "skipped": skipped,
                "failed": failed, "errors": errors[:50]}
