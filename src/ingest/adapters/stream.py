from __future__ import annotations

from ..model import (
    Acquisition,
    SourceRef,
    StreamSource,
    StreamingAcquisition,
    now_iso,
)
from ..policy import IngestPolicy
from .base import AcquisitionFailed, PolicyRejected


class StreamAdapter:
    name = "stream"
    version = "1"

    def supports(self, source) -> bool:
        return isinstance(source, StreamSource)

    @staticmethod
    def _validate_source(source: StreamSource) -> None:
        if not isinstance(source.locator, str) or not source.locator.strip():
            raise PolicyRejected("stream locator must be non-empty")

    @staticmethod
    def _source_identity(source: StreamSource) -> dict:
        if source.source_identity:
            return dict(source.source_identity)
        return {"locator": source.locator}

    @staticmethod
    def _validated_chunks(source: StreamSource):
        try:
            for chunk in source.chunks:
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise AcquisitionFailed(
                        "caller stream chunks must be bytes-like"
                    )
                yield bytes(chunk)
        except AcquisitionFailed:
            raise
        except Exception as exc:
            raise AcquisitionFailed("caller stream failed") from exc

    def _source_ref(self, source: StreamSource) -> SourceRef:
        return SourceRef(
            scheme="stream",
            locator=source.locator,
            adapter=self.name,
            adapter_version=self.version,
            observed_at=now_iso(),
            source_identity=self._source_identity(source),
        )

    def acquire_stream(
        self,
        source: StreamSource,
        policy: IngestPolicy,
    ) -> StreamingAcquisition:
        self._validate_source(source)
        return StreamingAcquisition(
            chunks=self._validated_chunks(source),
            source=self._source_ref(source),
            claimed_media_type=source.media_type,
        )

    def acquire(
        self,
        source: StreamSource,
        policy: IngestPolicy,
    ) -> Acquisition:
        self._validate_source(source)
        chunks: list[bytes] = []
        total = 0
        for chunk in self._validated_chunks(source):
            total += len(chunk)
            if total > policy.max_bytes:
                raise PolicyRejected(
                    f"stream exceeds max_bytes={policy.max_bytes}"
                )
            chunks.append(chunk)
        return Acquisition(
            data=b"".join(chunks),
            source=self._source_ref(source),
            claimed_media_type=source.media_type,
        )
