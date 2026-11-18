"""Structured JSON logging with PII scrubbing.

Rule: no PII in logs. Keys known to carry sensitive data are replaced, and values that look
like SSNs/TINs/emails are masked even under innocuous keys.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "session_token",
        "secret",
        "authorization",
        "cookie",
        "ssn",
        "tin",
        "fein",
        "ein",
        "email",
        "totp_secret",
        "api_key",
        "account_number",
        "routing_number",
    }
)
_SSN_RE = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
_EIN_RE = re.compile(r"\b\d{2}-\d{7}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        value = _SSN_RE.sub("[REDACTED-TIN]", value)
        value = _EIN_RE.sub("[REDACTED-TIN]", value)
        return _EMAIL_RE.sub("[REDACTED-EMAIL]", value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _is_sensitive(k) else scrub_value(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [scrub_value(v) for v in value]
    return value


def _is_sensitive(key: object) -> bool:
    return isinstance(key, str) and key.lower() in SENSITIVE_KEYS


def scrub_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        if _is_sensitive(key):
            event_dict[key] = "[REDACTED]"
        else:
            event_dict[key] = scrub_value(event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO", json: bool = True, service: str = "compback") -> None:
    renderer: Any = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            scrub_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
