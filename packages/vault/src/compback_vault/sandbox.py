"""Run untrusted-input processing in a separate process with CPU, memory and wall-clock limits."""

from __future__ import annotations

import multiprocessing as mp
import resource
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

DEFAULT_TIMEOUT_S = 300
DEFAULT_MEMORY_MB = 2048


class SandboxTimeoutError(TimeoutError):
    pass


class SandboxCrashError(RuntimeError):
    pass


def _child(
    conn: Connection, func: Callable[..., Any], args: tuple[Any, ...], mem_mb: int, cpu_s: int
) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        conn.send(("ok", func(*args)))
    except BaseException as exc:  # noqa: BLE001 - everything is reported to the parent
        try:
            conn.send(("err", exc))
        except Exception:  # noqa: BLE001 - unpicklable exception
            conn.send(("err", RuntimeError(f"{type(exc).__name__}: {exc}")))
    finally:
        conn.close()


def run_isolated(
    func: Callable[..., Any],
    *args: Any,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    memory_mb: int = DEFAULT_MEMORY_MB,
) -> Any:
    """Call ``func(*args)`` in a fresh process; re-raise its exception in the parent."""
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, func, args, memory_mb, timeout_s), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout_s):
            raise SandboxTimeoutError(f"processing exceeded {timeout_s}s")
        try:
            status, value = parent.recv()
        except EOFError as exc:
            raise SandboxCrashError("processing crashed (resource limit or fatal error)") from exc
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        parent.close()
    if status == "err":
        raise value
    return value
