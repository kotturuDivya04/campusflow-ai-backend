"""
Free Slot Engine (pure, deterministic).

Implements the brief's conceptual formula:

    Available Slot =
        Academic Slot
        - Teaching Classes
        - Lunch or Break Slots
        - Approved Appointment Conflicts
        - Event Conflicts
        - Buffer Conflicts
        - Dated Busy Blocks

The engine is intentionally free of database and ORM concerns: it receives
already-resolved plain data (academic slots for the date, the sets of occupied
slot ids by reason, and the buffer) and returns candidate slots in chronological
order. FreeSlotService (repository-backed) supplies those inputs.

=== Documented conflict & capacity behaviour ===============================
* CAPACITY is 1 per (faculty, date, academic_slot). A slot holding an APPROVED
  appointment (or an active queue entry) is occupied.
* PENDING requests do NOT occupy a slot (brief: "Do not treat pending requests
  as permanently occupying a slot unless capacity rules require it"). They are
  advisory only; two students may hold pending requests on the same slot and the
  faculty approves at most one.
* LUNCH/BREAK: the seeded academic_slots contain no lunch/break rows — lunch is
  encoded as the GAP between Period 4 (ends 12:20) and Period 5 (starts 13:30),
  so it never appears as a candidate. For robustness against other datasets the
  engine still drops any slot whose name matches BREAK_NAME_PATTERNS.
* EVENT CONFLICTS: DEFERRED. The canonical `events` table links to clubs
  (events.organizing_club_id), not faculty, and `venue_bookings` links
  classrooms/users — so the schema exposes no faculty-to-event relationship.
  No event slots are excluded. The `event_slot_ids` parameter is retained so the
  feature can be enabled with no engine change once such a relationship exists.
  Documented in SCHEMA_CAPABILITY_MAP.md and VERIFICATION_REPORT.md.
* BUFFER: every occupied interval is expanded by `buffer_minutes` on both sides;
  a candidate free slot intersecting any expanded occupied interval is dropped.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from app.services.domain import Occupancy, SlotView

BREAK_NAME_PATTERNS = ("lunch", "break", "recess", "interval", "tea")


def _looks_like_break(slot: SlotView) -> bool:
    name = slot.slot_name.strip().lower()
    return any(p in name for p in BREAK_NAME_PATTERNS)


def compute_free_slots(
    *,
    academic_slots: Sequence[SlotView],
    teaching_slot_ids: Iterable[int],
    approved_appointment_slot_ids: Iterable[int],
    busy_slot_ids: Iterable[int],
    event_slot_ids: Iterable[int] = (),
    buffer_minutes: int = 0,
) -> list[SlotView]:
    """Return the candidate free slots in chronological order (start_time asc)."""
    teaching = set(teaching_slot_ids)
    approved = set(approved_appointment_slot_ids)
    busy = set(busy_slot_ids)
    events = set(event_slot_ids)

    ordered = sorted(academic_slots, key=lambda s: (s.start_min(), s.id))

    # Steps 2-6: build the set of occupied slots (by any reason) and the
    # provisional free set (everything not directly occupied).
    occupied_ids: set[int] = set()
    free: list[SlotView] = []
    for s in ordered:
        if s.id in teaching:
            occupied_ids.add(s.id); continue          # step 4: teaching
        if _looks_like_break(s):
            occupied_ids.add(s.id); continue          # step 5: lunch/break
        if s.id in approved:
            occupied_ids.add(s.id); continue          # step 6: approved appts
        if s.id in events:
            occupied_ids.add(s.id); continue          # step 7: event conflicts
        if s.id in busy:
            occupied_ids.add(s.id); continue          # step 9: dated busy
        free.append(s)

    if buffer_minutes <= 0:
        return free  # step 10: already chronological

    # Step 8: buffer. Expand each occupied interval by the buffer and drop any
    # candidate that intersects an expanded window.
    occ_intervals = [
        (s.start_min() - buffer_minutes, s.end_min() + buffer_minutes)
        for s in ordered if s.id in occupied_ids
    ]
    kept: list[SlotView] = []
    for s in free:
        cs, ce = s.start_min(), s.end_min()
        if any(cs < oe and ce > os for (os, oe) in occ_intervals):
            continue
        kept.append(s)
    return kept


def explain_unavailable(
    *,
    slot: SlotView,
    occupancies: Sequence[Occupancy],
) -> str:
    """Deterministic, human-readable reason a specific slot is unavailable."""
    reasons = [o for o in occupancies if o.slot_id == slot.id]
    if not reasons:
        return f"Slot '{slot.slot_name}' is available."
    parts = []
    for o in reasons:
        label = {
            "TEACHING": "a scheduled class",
            "BREAK": "a lunch/break period",
            "APPOINTMENT": "an already-approved appointment",
            "EVENT": "an approved event",
            "BUSY": "a faculty-marked busy block",
            "BUFFER": "the meeting buffer around an adjacent commitment",
        }.get(o.kind, o.kind.lower())
        parts.append(label + (f" ({o.detail})" if o.detail else ""))
    return f"Slot '{slot.slot_name}' is unavailable due to " + "; ".join(parts) + "."
