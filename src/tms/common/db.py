"""Database setup (SQLite through SQLAlchemy) and the shared ``intersections`` table.

Each module defines its own tables in its own ``models.py``; ``init_db`` imports them all
so ``create_all`` sees every table. ``configure`` can be called again to point the app at a
different database (the tests use an in-memory one).
"""
from __future__ import annotations

import importlib
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy import DateTime, Integer, String, Text, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from tms.common import clock


class Base(DeclarativeBase):
    pass


class Intersection(Base):
    """Minimal shared table; Roshini's admin module adds versioning and history on top."""

    __tablename__ = "intersections"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[str] = mapped_column(Text, default="{}")  # JSON, merged with defaults on read
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)


MODEL_MODULES = (
    "tms.admin.models",
    "tms.signal_control.models",
    "tms.detection.models",
    "tms.simulation.models",
    "tms.incident.models",
)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure(database_url: str) -> Engine:
    """(Re)create the engine and session factory for ``database_url``."""
    global _engine, _session_factory
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if database_url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool  # one shared in-memory database
    else:
        kwargs["connect_args"]["timeout"] = 30
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite") and "memory" not in database_url and database_url != "sqlite://":

        @event.listens_for(engine, "connect")
        def _wal(dbapi_connection, _):  # noqa: ANN001
            dbapi_connection.execute("PRAGMA journal_mode=WAL")

    _engine = engine
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)
    return engine


def init_db() -> None:
    if _engine is None:
        raise RuntimeError("Call db.configure(url) first")
    for module in MODEL_MODULES:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name is None or not module.startswith(exc.name):
                raise  # a real missing dependency, not a module that is not merged yet
    Base.metadata.create_all(bind=_engine)


def new_session() -> Session:
    if _session_factory is None:
        raise RuntimeError("Call db.configure(url) first")
    return _session_factory()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = new_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    session = new_session()
    try:
        yield session
    finally:
        session.close()



def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Call db.configure(url) first")
    return _engine
