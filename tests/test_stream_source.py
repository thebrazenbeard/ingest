import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingest import (
    FileSystemStore,
    IngestPolicy,
    IngestStatus,
    Ingestor,
    StreamSource,
)


class StreamSourceTests(unittest.TestCase):
    def test_stream_source_uses_bounded_streaming_cas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            source = StreamSource(
                [b"\x00alpha", b"beta"],
                locator="urn:stream:one",
                media_type="application/octet-stream",
            )

            with patch.object(
                store,
                "put_blob_stream",
                wraps=store.put_blob_stream,
            ) as stream_put:
                result = Ingestor(store).ingest(source)

            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            stream_put.assert_called_once()
            self.assertEqual(result.source.scheme, "stream")
            self.assertEqual(
                result.source.source_identity,
                {"locator": "urn:stream:one"},
            )
            self.assertEqual(
                (root / result.raw_artifact.storage_locator).read_bytes(),
                b"\x00alphabeta",
            )

    def test_stream_source_iterator_failure_fails_without_raw_blob(self):
        def broken():
            yield b"prefix"
            raise RuntimeError("upstream exploded")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            result = Ingestor(FileSystemStore(root)).ingest(
                StreamSource(broken(), locator="urn:stream:broken")
            )

            self.assertEqual(result.status, IngestStatus.FAILED)
            self.assertIn("caller stream failed", result.error)
            blobs = root / "blobs"
            published = [] if not blobs.exists() else [
                p for p in blobs.rglob("*")
                if p.is_file() and not p.name.startswith(".tmp-")
            ]
            self.assertEqual(published, [])

    def test_stream_source_rejects_non_bytes_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Ingestor(
                FileSystemStore(Path(tmp) / ".ingest")
            ).ingest(
                StreamSource(
                    [b"ok", "not-bytes"],
                    locator="urn:stream:type",
                )
            )

            self.assertEqual(result.status, IngestStatus.FAILED)
            self.assertIn("bytes-like", result.error)

    def test_stream_source_obeys_max_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Ingestor(
                FileSystemStore(Path(tmp) / ".ingest")
            ).ingest(
                StreamSource(
                    [b"abc", b"def"],
                    locator="urn:stream:limit",
                ),
                IngestPolicy(max_bytes=5),
            )

            self.assertEqual(result.status, IngestStatus.REJECTED)
            self.assertIn("max_bytes=5", result.error)

    def test_stream_source_identity_is_stable_across_fresh_iterables(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            first = Ingestor(store).ingest(
                StreamSource([b"\x00same"], locator="urn:stream:same")
            )
            second = Ingestor(store).ingest(
                StreamSource([b"\x00same"], locator="urn:stream:same")
            )

            self.assertEqual(first.status, IngestStatus.ACCEPTED)
            self.assertEqual(second.status, IngestStatus.DUPLICATE)
            self.assertEqual(first.ingest_id, second.ingest_id)


if __name__ == "__main__":
    unittest.main()
