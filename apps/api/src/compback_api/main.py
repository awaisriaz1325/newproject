"""FastAPI application factory."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from compback_api.routes import (
    analysis,
    auth,
    documents,
    extractions,
    health,
    jurisdictions,
    orgs,
)
from compback_core.config import Settings, get_settings
from compback_core.logs import configure_logging, get_logger

log = get_logger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json, f"{settings.service_name}-api")
    app = FastAPI(
        title="CompBack API",
        version="0.1.0",
        docs_url="/docs" if settings.env.value in ("dev", "test") else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.env.value in ("dev", "test") else None,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Org-Id"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if settings.cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        response.headers["X-Request-Id"] = request_id
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(orgs.router)
    app.include_router(jurisdictions.router)
    app.include_router(documents.router)
    app.include_router(extractions.router)
    app.include_router(analysis.router)
    return app


app = create_app()
