"""
Database initialisation.

Migration strategy (deliberately simple and reviewable for a competition MVP):

    001_core_schema.sql      the FINALIZED schema, verbatim. Never edited.
    002_mvp_operational.sql  the two strictly-additive MVP tables plus the
                             scheduling rows inserted into system_settings.

`python -m app.db.init_db` applies them in order and is idempotent enough to
re-run (002 uses IF NOT EXISTS / ON CONFLICT DO NOTHING). An Alembic scaffold is
also included (alembic/) for teams that prefer versioned migrations; both paths
produce the same schema.
"""
from __future__ import annotations

import pathlib
import sys

from sqlalchemy import text

from app.db.session import engine

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "migrations"
ORDER = ("001_core_schema.sql", "002_mvp_operational.sql")


def apply_sql_file(path: pathlib.Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"applied {path.name}")


def init_db(include_seed: bool = False) -> None:
    for name in ORDER:
        path = MIGRATIONS / name
        if not path.exists():
            raise SystemExit(f"missing migration file: {path}")
        apply_sql_file(path)
    if include_seed:
        seed = MIGRATIONS / "003_seed.sql"
        if seed.exists():
            apply_sql_file(seed)
        else:
            print("no 003_seed.sql present; skipping seed")
    print("database initialised")


if __name__ == "__main__":
    init_db(include_seed="--seed" in sys.argv)
