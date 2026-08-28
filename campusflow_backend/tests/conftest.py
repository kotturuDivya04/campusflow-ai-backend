"""
Pytest configuration.

The suite is split in two:

  * PURE tests (test_free_slot_engine, test_priority_eta, test_transitions,
    test_queue, test_importer, test_ai) — standard library only. They run under
    `python -m unittest discover -s tests` with NOTHING installed.
  * INTEGRATION tests (test_api) — need fastapi, httpx, SQLAlchemy and a
    reachable PostgreSQL. They are skipped automatically when those are absent
    so the pure suite always stays green.
"""
from __future__ import annotations

import importlib.util

import pytest


def _have(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


requires_web_stack = pytest.mark.skipif(
    not (_have("fastapi") and _have("httpx") and _have("sqlalchemy")),
    reason="fastapi/httpx/sqlalchemy not installed in this environment",
)
