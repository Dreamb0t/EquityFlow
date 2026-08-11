"""
Engine/session setup. DATABASE_URL comes from config.settings so switching to a
server DB later (for the web version) is a one-line env change.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from stockapp.config.settings import settings
from stockapp.data.orm_models import Base

engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

# (table, column, DDL type) pairs added after the initial release. create_all()
# only creates missing *tables*, not missing *columns* on tables that already
# exist — so anyone with a DB from before this column was added needs it
# patched in, hence the tiny migration below.
_ADDED_COLUMNS = [
    ("positions", "currency", "VARCHAR DEFAULT 'USD'"),
    ("watchlist", "currency", "VARCHAR DEFAULT 'USD'"),
]


def _migrate(conn) -> None:
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    for table, column, ddl_type in _ADDED_COLUMNS:
        if table not in existing_tables:
            continue  # create_all() below will create it with the column already
        columns = {c["name"] for c in inspector.get_columns(table)}
        if column not in columns:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def init_db() -> None:
    """Create tables if they don't exist, and patch in columns added after a
    table already existed. Call once at app startup."""
    with engine.begin() as conn:
        _migrate(conn)
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
