from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .canonical import canonical_json, sha256_bytes
from .model import Artifact


class StoreConflict(RuntimeError):
    pass


class FileSystemStore:
    def __init__(self, root: str | Path = ".ingest"):
        self.root = Path(root)
        self._ensure_directory_chain(self.root)

    @staticmethod
    def _is_link_like(path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return bool(is_junction is not None and is_junction())

    def _assert_no_managed_links(self, path: Path) -> None:
        path = Path(path)
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise StoreConflict(f"storage path escapes root: {path}") from exc

        current = self.root
        for part in relative.parts:
            current = current / part
            if self._is_link_like(current):
                raise StoreConflict(
                    f"managed storage path cannot be a symlink or junction: {current}"
                )

    def _ensure_directory_chain(self, path: Path) -> None:
        path = Path(path)
        self._assert_no_managed_links(path)
        if path.exists():
            if not path.is_dir():
                raise NotADirectoryError(path)
            return

        missing: list[Path] = []
        cursor = path
        while not cursor.exists():
            missing.append(cursor)
            parent = cursor.parent
            if parent == cursor:
                break
            cursor = parent

        if cursor.exists() and not cursor.is_dir():
            raise NotADirectoryError(cursor)

        for directory in reversed(missing):
            try:
                directory.mkdir()
            except FileExistsError:
                if not directory.is_dir():
                    raise
            self._assert_no_managed_links(directory)
            self._fsync_directory(directory.parent)

    @staticmethod
    def _fsync_directory(path: Path) -> bool:
        if os.name == "nt":
            return False
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            fd = os.open(path, flags)
        except OSError:
            return False
        try:
            os.fsync(fd)
        except OSError:
            return False
        finally:
            os.close(fd)
        return True

    def _atomic_create(self, path: Path, data: bytes) -> bool:
        self._ensure_directory_chain(path.parent)
        self._assert_no_managed_links(path)
        if path.exists():
            if path.read_bytes() != data:
                raise StoreConflict(f"immutable path collision: {path}")
            return False
        fd, temp_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._assert_no_managed_links(path.parent)
            try:
                os.link(temp_name, path)
            except FileExistsError:
                self._assert_no_managed_links(path)
                if path.read_bytes() != data:
                    raise StoreConflict(f"immutable path collision: {path}")
                return False
            self._fsync_directory(path.parent)
            return True
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def put_blob(self, data: bytes, *, media_type: str, kind: str) -> tuple[Artifact, bool]:
        digest = sha256_bytes(data)
        relative = Path("blobs") / "sha256" / digest[:2] / digest
        created = self._atomic_create(self.root / relative, data)
        return (
            Artifact(
                artifact_id=f"sha256:{digest}",
                sha256=digest,
                size_bytes=len(data),
                media_type=media_type,
                kind=kind,
                storage_locator=relative.as_posix(),
            ),
            created,
        )

    def _put_json(self, category: str, record_id: str, value: dict[str, Any]) -> bool:
        data = (canonical_json(value) + "\n").encode("utf-8")
        return self._atomic_create(self.root / category / f"{record_id}.json", data)

    def put_record(self, ingest_id: str, value: dict[str, Any]) -> bool:
        return self._put_json("records", ingest_id, value)

    def put_receipt(self, receipt_id: str, value: dict[str, Any]) -> bool:
        return self._put_json("receipts", receipt_id, value)

    def put_derivation(self, derivation_id: str, value: dict[str, Any]) -> bool:
        return self._put_json("derivations", derivation_id, value)

    def has_record(self, ingest_id: str) -> bool:
        return (self.root / "records" / f"{ingest_id}.json").is_file()

    def _get_json(self, category: str, record_id: str) -> dict[str, Any]:
        path = self.root / category / f"{record_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def get_record(self, ingest_id: str) -> dict[str, Any]:
        return self._get_json("records", ingest_id)

    def get_receipt(self, receipt_id: str) -> dict[str, Any]:
        return self._get_json("receipts", receipt_id)

    def get_derivation(self, derivation_id: str) -> dict[str, Any]:
        return self._get_json("derivations", derivation_id)
