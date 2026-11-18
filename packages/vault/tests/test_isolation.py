"""Sandbox limits, malware scanner protocol, storage key safety."""

from __future__ import annotations

import socket
import struct
import threading

import pytest

from compback_vault._testing import allocate_mb, raise_value_error, sleep_then_return
from compback_vault.malware import EICAR, ClamdScanner, TestSignatureScanner, Verdict
from compback_vault.sandbox import SandboxCrashError, SandboxTimeoutError, run_isolated
from compback_vault.storage import LocalObjectStore


def test_sandbox_returns_value() -> None:
    assert run_isolated(sleep_then_return, 0, timeout_s=30) == "done"


def test_sandbox_timeout_kills_child() -> None:
    with pytest.raises(SandboxTimeoutError):
        run_isolated(sleep_then_return, 10, timeout_s=1)


def test_sandbox_memory_cap() -> None:
    with pytest.raises((SandboxCrashError, MemoryError)):
        run_isolated(allocate_mb, 1024, timeout_s=30, memory_mb=256)


def test_sandbox_propagates_exceptions() -> None:
    with pytest.raises(ValueError, match="bad input"):
        run_isolated(raise_value_error, timeout_s=30)


def _fake_clamd(reply: bytes) -> tuple[int, threading.Thread]:
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def serve() -> None:
        conn, _ = srv.accept()
        with conn:
            assert conn.recv(10) == b"zINSTREAM\0"
            while True:
                (size,) = struct.unpack(">I", conn.recv(4, socket.MSG_WAITALL))
                if size == 0:
                    break
                conn.recv(size, socket.MSG_WAITALL)
            conn.sendall(reply)
        srv.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return port, thread


@pytest.mark.parametrize(
    ("reply", "verdict"),
    [
        (b"stream: OK\0", Verdict.CLEAN),
        (b"stream: Win.Test.EICAR_HDB-1 FOUND\0", Verdict.INFECTED),
        (b"INSTREAM size limit exceeded. ERROR\0", Verdict.ERROR),
    ],
)
def test_clamd_protocol(reply: bytes, verdict: Verdict) -> None:
    port, thread = _fake_clamd(reply)
    result = ClamdScanner("127.0.0.1", port, timeout=5).scan(b"x" * 200_000)
    thread.join(5)
    assert result.verdict == verdict
    if verdict == Verdict.INFECTED:
        assert result.signature == "Win.Test.EICAR_HDB-1"


def test_clamd_unreachable_is_error_not_clean() -> None:
    assert ClamdScanner("127.0.0.1", 1, timeout=1).scan(b"x").verdict == Verdict.ERROR


def test_test_scanner_flags_eicar() -> None:
    assert TestSignatureScanner().scan(b"abc" + EICAR).verdict == Verdict.INFECTED


@pytest.mark.parametrize("key", ["../x", "/abs", "a/../../b", "a//b", ""])
def test_storage_rejects_traversal(tmp_path: object, key: str) -> None:
    store = LocalObjectStore(str(tmp_path))
    with pytest.raises(ValueError, match="invalid object key"):
        store.put(key, b"x")
