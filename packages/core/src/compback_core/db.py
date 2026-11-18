"""Database engine, sessions, and tenant context.

Every tenant-scoped transaction sets ``app.org_id`` and ``app.user_id`` with
``set_config(..., is_local => true)`` so Postgres RLS policies apply. The app role is not the
table owner and has no BYPASSRLS, so a missing ``WHERE org_id = ...`` cannot leak data.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from compback_core.config import get_settings


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    dsn = url or settings.database_url.get_secret_value()
    return create_engine(dsn, pool_size=settings.db_pool_size, pool_pre_ping=True, future=True)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)


def set_tenant_context(
    session: Session,
    *,
    org_id: uuid.UUID | None,
    user_id: uuid.UUID | None = None,
    actor_kind: str = "user",
) -> None:
    """Bind tenant/actor for the current transaction (transaction-local GUCs)."""
    session.execute(
        text(
            "SELECT set_config('app.org_id', :org, true), "
            "set_config('app.user_id', :uid, true), "
            "set_config('app.actor_kind', :kind, true)"
        ),
        {
            "org": str(org_id) if org_id else "",
            "uid": str(user_id) if user_id else "",
            "kind": actor_kind,
        },
    )


@contextmanager
def tenant_session(
    org_id: uuid.UUID | None,
    user_id: uuid.UUID | None = None,
    *,
    actor_kind: str = "user",
    engine: Engine | None = None,
) -> Iterator[Session]:
    """A transaction with tenant context applied; commits on success, rolls back on error."""
    factory = session_factory(engine)
    with factory() as session, session.begin():
        set_tenant_context(session, org_id=org_id, user_id=user_id, actor_kind=actor_kind)
        yield session


def check_database(engine: Engine | None = None) -> bool:
    with (engine or get_engine()).connect() as conn:
        return bool(conn.execute(text("SELECT 1")).scalar_one() == 1)
