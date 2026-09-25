from __future__ import annotations

import mimetypes
from pathlib import Path

from ..model import Acquisition, FileSource, SourceRef, now_iso
from ..policy import IngestPolicy
from .base import AcquisitionFailed, PolicyRejected


class FileAdapter:
    name = "file"
    version = "1"

    def supports(self, source) -> bool:
        return isinstance(source, FileSource)

    @staticmethod
    def _within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    def acquire(self, source: FileSource, policy: IngestPolicy) -> Acquisition:
        path = Path(source.path).expanduser()
        if not path.exists() or not path.is_file():
            raise AcquisitionFailed(f"file not found: {path}")
        if path.is_symlink() and not policy.follow_symlinks:
            raise PolicyRejected("symlink input is disabled by policy")
        resolved = path.resolve(strict=True)
        if policy.allowed_roots:
            roots = tuple(Path(root).expanduser().resolve(strict=True) for root in policy.allowed_roots)
            if not any(self._within(resolved, root) for root in roots):
                raise PolicyRejected("file resolves outside allowed_roots")
        size = resolved.stat().st_size
        if size > policy.max_bytes:
            raise PolicyRejected(f"file exceeds max_bytes={policy.max_bytes}")
        data = resolved.read_bytes()
        if len(data) > policy.max_bytes:
            raise PolicyRejected(f"file exceeds max_bytes={policy.max_bytes}")
        media_type, _ = mimetypes.guess_type(resolved.name)
        if resolved.suffix.lower() == ".jsonl":
            media_type = "application/x-ndjson"
        return Acquisition(
            data=data,
            source=SourceRef(
                scheme="file",
                locator=str(resolved),
                adapter=self.name,
                adapter_version=self.version,
                observed_at=now_iso(),
                source_identity={"resolved_path": str(resolved)},
                observed_metadata={"size_bytes": size},
            ),
            claimed_media_type=media_type,
        )
