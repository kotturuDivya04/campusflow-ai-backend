"""
Engine + session factory + FastAPI dependency.

A single Engine is created from settings.DATABASE_URL. get_db yields a session
per request and always closes it (dependency injection, brief requirement). The
import is lazy-friendly: creating the engine does not connect until first use.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False,
                            expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
