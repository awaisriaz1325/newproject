"""Liveness and readiness probes."""

from __future__ import annotations

from compback_core.db import check_database
from fastapi import APIRouter, Response, status
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness() -> dict[str, str]:
    """Process is up. Never touches dependencies."""
    return {"status": "ok"}


@router.get("/readyz")
def readiness(response: Response) -> dict[str, str]:
    """Dependencies reachable. Returns 503 when the database is unavailable."""
    try:
        db_ok = check_database()
    except SQLAlchemyError:
        db_ok = False
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "down"}
    return {"status": "ok", "database": "up"}
