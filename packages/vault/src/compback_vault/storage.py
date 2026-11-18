"""Object storage. Objects are envelope-encrypted by the caller before ``put``; buckets are private.

Downloads never hand out bucket URLs: the API streams content after authorization, auditing and
watermarking (see ``compback_api.routes.documents``). Bucket SSE is enabled as defence in depth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from compback_core.config import Settings, get_settings


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class ObjectNotFoundError(KeyError):
    pass


def _safe_key(key: str) -> str:
    parts = key.split("/")
    if not key or key.startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise ValueError("invalid object key")
    return key


class LocalObjectStore:
    """Filesystem store for dev/test. Rejected in staging/prod by config validation."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / _safe_key(key)).resolve()
        if self._root not in path.parents:
            raise ValueError("invalid object key")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise ObjectNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3ObjectStore:
    """S3-compatible store (AWS S3, Cloudflare R2). Requests SSE-S3 on every write."""

    def __init__(self, bucket: str, endpoint_url: str | None, region: str | None) -> None:
        import boto3  # noqa: PLC0415 - only needed when S3 storage is configured

        self._bucket = bucket
        self._s3: Any = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    def put(self, key: str, data: bytes) -> None:
        self._s3.put_object(
            Bucket=self._bucket, Key=_safe_key(key), Body=data, ServerSideEncryption="AES256"
        )

    def get(self, key: str) -> bytes:
        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=_safe_key(key))
        except self._s3.exceptions.NoSuchKey as exc:
            raise ObjectNotFoundError(key) from exc
        return bytes(obj["Body"].read())

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=_safe_key(key))

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=_safe_key(key))
        except Exception:  # noqa: BLE001 - botocore ClientError for 404
            return False
        return True


def store_from_settings(settings: Settings | None = None) -> ObjectStore:
    settings = settings or get_settings()
    if settings.storage_backend == "local":
        return LocalObjectStore(settings.storage_local_root)
    if settings.storage_backend == "s3":
        return S3ObjectStore(
            settings.storage_bucket, settings.storage_endpoint_url, settings.storage_region
        )
    raise RuntimeError(f"unknown storage backend: {settings.storage_backend}")
