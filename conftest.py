"""Shared pytest configuration: test environment defaults (no network, no real secrets)."""

from __future__ import annotations

import base64
import os

os.environ.setdefault("COMPBACK_ENV", "test")
os.environ.setdefault("COMPBACK_LOG_JSON", "true")
os.environ.setdefault("COMPBACK_COOKIE_SECURE", "false")
os.environ.setdefault(
    "COMPBACK_DATABASE_URL",
    "postgresql+psycopg://compback_app:compback_app@localhost:5432/compback_test",
)
os.environ.setdefault(
    "COMPBACK_DATABASE_OWNER_URL",
    "postgresql+psycopg://compback_owner:compback_owner@localhost:5432/compback_test",
)
# Deterministic test-only master key (never used outside tests).
os.environ.setdefault("COMPBACK_LOCAL_MASTER_KEY_B64", base64.b64encode(b"t" * 32).decode())
