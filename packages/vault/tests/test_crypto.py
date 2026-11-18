import os

import pytest
from hypothesis import given
from hypothesis import strategies as st

from compback_vault.crypto import DecryptionError, Envelope, LocalKeyProvider

ENV = Envelope(LocalKeyProvider(os.urandom(32)))


@given(st.binary(max_size=4096), st.text(max_size=50))
def test_roundtrip(data: bytes, ctx: str) -> None:
    assert ENV.decrypt(ENV.encrypt(data, ctx), ctx) == data


def test_context_binding_prevents_row_swap() -> None:
    blob = ENV.encrypt(b"12-3456789", "employers.fein:org-a")
    with pytest.raises(DecryptionError):
        ENV.decrypt(blob, "employers.fein:org-b")


def test_tamper_detected() -> None:
    blob = bytearray(ENV.encrypt(b"secret", "c"))
    blob[-1] ^= 0x01
    with pytest.raises(DecryptionError):
        ENV.decrypt(bytes(blob), "c")


def test_other_master_key_cannot_decrypt() -> None:
    other = Envelope(LocalKeyProvider(os.urandom(32)))
    with pytest.raises(DecryptionError):
        other.decrypt(ENV.encrypt(b"x", "c"), "c")


@pytest.mark.parametrize("blob", [b"", b"XX", b"CB1\x00", b"CB1\x00\x05abc"])
def test_malformed(blob: bytes) -> None:
    with pytest.raises(DecryptionError):
        ENV.decrypt(blob, "c")


def test_nondeterministic() -> None:
    assert ENV.encrypt(b"same", "c") != ENV.encrypt(b"same", "c")


def test_bad_master_key_length() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        LocalKeyProvider(b"short")
