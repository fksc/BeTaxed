"""Object storage backends (GCS CMEK in prod, local dir in DEV)."""

from __future__ import annotations

import hashlib
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.settings import (
    get_gcs_bucket,
    get_gcs_kms_key_name,
    get_local_storage_dir,
)


class ObjectStorage(ABC):
    @abstractmethod
    def put_bytes(
        self,
        data: bytes,
        *,
        object_name: str,
        content_type: str | None = None,
    ) -> str:
        """Store bytes and return the storage path (GCS URI or local path)."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Remove object at path."""

    @abstractmethod
    def get_bytes(self, storage_path: str) -> bytes:
        """Read object bytes."""


class LocalObjectStorage(ObjectStorage):
    """DEV fallback when GCS_BUCKET is unset."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        data: bytes,
        *,
        object_name: str,
        content_type: str | None = None,
    ) -> str:
        rel = object_name.lstrip("/")
        dest = self._root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def delete(self, storage_path: str) -> None:
        path = Path(storage_path)
        if path.is_file():
            path.unlink()

    def get_bytes(self, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()


class GcsObjectStorage(ObjectStorage):
    """GCS with CMEK — objects encrypted at rest by Cloud KMS."""

    def __init__(self, bucket_name: str, kms_key_name: str | None) -> None:
        from google.cloud import storage

        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket_name)
        self._kms_key_name = kms_key_name

    def put_bytes(
        self,
        data: bytes,
        *,
        object_name: str,
        content_type: str | None = None,
    ) -> str:
        blob = self._bucket.blob(object_name.lstrip("/"))
        if self._kms_key_name:
            blob.kms_key_name = self._kms_key_name
        blob.upload_from_string(
            data,
            content_type=content_type or "application/octet-stream",
        )
        return f"gs://{self._bucket.name}/{blob.name}"

    def delete(self, storage_path: str) -> None:
        if not storage_path.startswith("gs://"):
            raise ValueError("expected gs:// path")
        without = storage_path[5:]
        bucket_name, _, object_name = without.partition("/")
        bucket = self._client.bucket(bucket_name)
        bucket.blob(object_name).delete()

    def get_bytes(self, storage_path: str) -> bytes:
        if not storage_path.startswith("gs://"):
            raise ValueError("expected gs:// path")
        without = storage_path[5:]
        bucket_name, _, object_name = without.partition("/")
        bucket = self._client.bucket(bucket_name)
        return bucket.blob(object_name).download_as_bytes()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_object_name(
    *,
    company_id: uuid.UUID | None,
    intake_id: uuid.UUID | None,
    filename: str,
) -> str:
    scope = f"company/{company_id}" if company_id else f"intake/{intake_id}"
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"{scope}/{uuid.uuid4().hex}/{safe_name}"


def get_object_storage() -> ObjectStorage:
    bucket = get_gcs_bucket()
    if bucket:
        return GcsObjectStorage(bucket, get_gcs_kms_key_name())
    return LocalObjectStorage(get_local_storage_dir())
