"""Envelope encryption (ADR-0010).

Each value gets a fresh 256-bit data key (DEK). The DEK encrypts the value with AES-256-GCM and is
itself wrapped by a master key held by a ``KeyProvider`` (local key for dev/test, AWS KMS in prod).
Associated data (AAD) binds a ciphertext to its context (e.g. ``users.totp_secret:<user_id>``) so
it cannot be copied to another row or tenant and still decrypt.

Blob format v1:  b"CB1" | u16 wrapped_len | wrapped_dek | 12-byte nonce | ciphertext+tag
"""

from __future__ import annotations

import base64
import os
import struct
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from compback_core.config import Settings, get_settings

MAGIC = b"CB1"
NONCE_LEN = 12
KEY_LEN = 32


class DecryptionError(Exception):
    """Ciphertext is malformed, tampered with, or bound to a different context."""


class KeyProvider(Protocol):
    def generate_data_key(self) -> tuple[bytes, bytes]:
        """Return (plaintext_dek, wrapped_dek)."""
        ...

    def unwrap(self, wrapped: bytes) -> bytes: ...


class LocalKeyProvider:
    """Wraps DEKs with a local AES-256-GCM master key. Dev/test only (blocked in prod by config)."""

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != KEY_LEN:
            raise ValueError("master key must be 32 bytes")
        self._aead = AESGCM(master_key)

    def generate_data_key(self) -> tuple[bytes, bytes]:
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(NONCE_LEN)
        return dek, nonce + self._aead.encrypt(nonce, dek, b"compback-dek-v1")

    def unwrap(self, wrapped: bytes) -> bytes:
        try:
            return self._aead.decrypt(wrapped[:NONCE_LEN], wrapped[NONCE_LEN:], b"compback-dek-v1")
        except Exception as exc:  # cryptography raises InvalidTag
            raise DecryptionError("cannot unwrap data key") from exc


class AwsKmsKeyProvider:
    """AWS KMS master key. Uses KMS GenerateDataKey / Decrypt; the master key never leaves KMS."""

    def __init__(self, key_id: str, region: str | None = None) -> None:
        import boto3  # noqa: PLC0415 - optional heavy dependency, only in prod

        self._key_id = key_id
        self._kms = boto3.client("kms", region_name=region)

    def generate_data_key(self) -> tuple[bytes, bytes]:
        resp = self._kms.generate_data_key(KeyId=self._key_id, KeySpec="AES_256")
        return bytes(resp["Plaintext"]), bytes(resp["CiphertextBlob"])

    def unwrap(self, wrapped: bytes) -> bytes:
        try:
            resp = self._kms.decrypt(CiphertextBlob=wrapped, KeyId=self._key_id)
        except Exception as exc:
            raise DecryptionError("KMS could not unwrap data key") from exc
        return bytes(resp["Plaintext"])


def provider_from_settings(settings: Settings | None = None) -> KeyProvider:
    settings = settings or get_settings()
    if settings.kms_backend == "local":
        if settings.local_master_key_b64 is None:
            raise RuntimeError(
                "COMPBACK_LOCAL_MASTER_KEY_B64 is required for the local KMS backend"
            )
        return LocalKeyProvider(base64.b64decode(settings.local_master_key_b64.get_secret_value()))
    if settings.kms_backend == "aws":
        if not settings.kms_key_id:
            raise RuntimeError("COMPBACK_KMS_KEY_ID is required for the aws KMS backend")
        return AwsKmsKeyProvider(settings.kms_key_id, settings.storage_region or None)
    raise RuntimeError(f"unknown kms backend: {settings.kms_backend}")


class Envelope:
    def __init__(self, provider: KeyProvider) -> None:
        self._provider = provider

    def encrypt(self, plaintext: bytes, context: str) -> bytes:
        dek, wrapped = self._provider.generate_data_key()
        nonce = os.urandom(NONCE_LEN)
        ct = AESGCM(dek).encrypt(nonce, plaintext, context.encode())
        return MAGIC + struct.pack(">H", len(wrapped)) + wrapped + nonce + ct

    def decrypt(self, blob: bytes, context: str) -> bytes:
        if len(blob) < len(MAGIC) + 2 or not blob.startswith(MAGIC):
            raise DecryptionError("unknown ciphertext format")
        (wlen,) = struct.unpack(">H", blob[3:5])
        wrapped = blob[5 : 5 + wlen]
        rest = blob[5 + wlen :]
        if len(wrapped) != wlen or len(rest) <= NONCE_LEN:
            raise DecryptionError("truncated ciphertext")
        dek = self._provider.unwrap(wrapped)
        try:
            return AESGCM(dek).decrypt(rest[:NONCE_LEN], rest[NONCE_LEN:], context.encode())
        except Exception as exc:
            raise DecryptionError("ciphertext invalid for this context") from exc

    def encrypt_str(self, value: str, context: str) -> bytes:
        return self.encrypt(value.encode(), context)

    def decrypt_str(self, blob: bytes, context: str) -> str:
        return self.decrypt(blob, context).decode()


def get_envelope() -> Envelope:
    return Envelope(provider_from_settings())
