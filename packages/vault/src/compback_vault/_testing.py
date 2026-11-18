"""Importable helpers for sandbox tests (spawned children must import their target function)."""

from __future__ import annotations

import time


def sleep_then_return(seconds: float) -> str:
    time.sleep(seconds)
    return "done"


def allocate_mb(mb: int) -> int:
    return len(bytearray(mb * 1024 * 1024))


def raise_value_error() -> None:
    raise ValueError("bad input")
