"""
Tests for the PURE parsing half of the timetable importer. These run with the
standard library alone (no database, no SQLAlchemy) because parsing was
deliberately separated from persistence.
"""
from __future__ import annotations

import json
import unittest

from app.services.timetable_importer import parse_csv, parse_json

HEADER = ("section_name,subject_code,faculty_code,classroom_number,"
          "slot_name,day_of_week,academic_year,semester")
GOOD = "CSE-3A,CS301,FAC001,A-101,Period 1,Monday,2026,Fall"


class ParseCsvTests(unittest.TestCase):
    def test_valid_row_parses(self):
        result = parse_csv(HEADER + "\n" + GOOD + "\n")
        self.assertIsNone(result.fatal)
        self.assertEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertIsNone(row.error)
        self.assertEqual(row.data["section_name"], "CSE-3A")
        self.assertEqual(row.data["academic_year"], 2026)  # coerced to int

    def test_missing_column_is_fatal(self):
        bad_header = HEADER.replace(",semester", "")
        result = parse_csv(bad_header + "\n")
        self.assertIsNotNone(result.fatal)
        self.assertIn("semester", result.fatal)

    def test_empty_file_is_fatal(self):
        self.assertIsNotNone(parse_csv("").fatal)

    def test_invalid_day_is_rejected_not_fatal(self):
        result = parse_csv(HEADER + "\n" + GOOD.replace("Monday", "Funday") + "\n")
        self.assertIsNone(result.fatal)
        self.assertIn("day_of_week", result.rows[0].error)

    def test_non_integer_year_is_rejected(self):
        result = parse_csv(HEADER + "\n" + GOOD.replace(",2026,", ",twenty,") + "\n")
        self.assertIn("academic_year", result.rows[0].error)

    def test_blank_value_is_rejected(self):
        result = parse_csv(HEADER + "\n" + GOOD.replace("FAC001", "") + "\n")
        self.assertIn("faculty_code", result.rows[0].error)

    def test_one_bad_row_does_not_abort_the_others(self):
        text = HEADER + "\n" + GOOD + "\n" + GOOD.replace("Monday", "Funday") + "\n"
        result = parse_csv(text)
        self.assertEqual(len(result.rows), 2)
        self.assertIsNone(result.rows[0].error)
        self.assertIsNotNone(result.rows[1].error)


class ParseJsonTests(unittest.TestCase):
    def _row(self, **over):
        base = dict(zip(HEADER.split(","), GOOD.split(",")))
        base.update(over)
        return base

    def test_valid_json_list(self):
        result = parse_json(json.dumps([self._row()]))
        self.assertIsNone(result.fatal)
        self.assertIsNone(result.rows[0].error)

    def test_invalid_json_is_fatal(self):
        self.assertIsNotNone(parse_json("{not json").fatal)

    def test_non_list_payload_is_fatal(self):
        self.assertIsNotNone(parse_json(json.dumps({"a": 1})).fatal)

    def test_non_object_row_is_rejected(self):
        result = parse_json(json.dumps(["oops"]))
        self.assertIsNotNone(result.rows[0].error)


if __name__ == "__main__":
    unittest.main()
