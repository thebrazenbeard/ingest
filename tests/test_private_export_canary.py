"""Synthetic-only private archive acquisition/custody characterization.

This is NOT a production ChatGPT export parser or admission path. Ingest stores
ZIP bytes as opaque evidence. The test-local ZIP preflight illustrates a gate
an independent private capture workflow would need; it does not qualify a
remote revision, an OS storage ACL, or any real conversation for use.
"""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import unittest
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from ingest import FileSystemStore, IngestPolicy, IngestStatus, Ingestor, StreamSource


def _synthetic_zip(entries: dict[str, bytes]) -> bytes:
    sink = BytesIO()
    with ZipFile(sink, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return sink.getvalue()


def _synthetic_preflight(payload: bytes) -> tuple[str, ...]:
    """Test-harness guard; intentionally not an installed input boundary."""
    if not payload or len(payload) > 256 * 1024:
        raise ValueError("synthetic archive byte limit")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            members = archive.infolist()
            if not members or len(members) > 16:
                raise ValueError("synthetic archive member limit")
            total = 0
            names: list[str] = []
            for member in members:
                name = member.filename
                parts = PurePosixPath(name).parts
                if (
                    not name
                    or name.startswith(("/", "\\"))
                    or "\\" in name
                    or re.match(r"^[A-Za-z]:", name)
                    or any(part in {"", ".", ".."} for part in name.split("/"))
                    or not parts
                ):
                    raise ValueError("synthetic archive unsafe member path")
                if member.flag_bits & 1:
                    raise ValueError("synthetic archive encrypted member")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("synthetic archive symlink member")
                if member.file_size > 128 * 1024:
                    raise ValueError("synthetic archive oversized member")
                total += member.file_size
                if total > 256 * 1024:
                    raise ValueError("synthetic archive inflated total limit")
                names.append(name)
            # This bounded fixture test decodes members for CRC. It is NOT a
            # general-purpose safe decompressor for adversarial ZIP formats.
            if archive.testzip() is not None:
                raise ValueError("synthetic archive corrupt member")
            return tuple(names)
    except BadZipFile as exc:
        raise ValueError("synthetic archive invalid ZIP") from exc


def _stream(payload: bytes, *, revision: str, locator: str = "synthetic:chat-export") -> StreamSource:
    def chunks():
        for offset in range(0, len(payload), 137):
            yield payload[offset : offset + 137]

    return StreamSource(
        chunks(),
        locator=locator,
        media_type="application/zip",
        source_identity={"synthetic_fixture": "chat-export", "claimed_revision": revision},
    )


class PrivateExportCanaryTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix="ingest-canary-")
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name) / "private-store"
        self.store = FileSystemStore(self.root)
        self.ingestor = Ingestor(self.store)
        self.payload = _synthetic_zip({
            "conversations.json": json.dumps([
                {"id": "synthetic-001", "title": "fictional sample", "mapping": {}}
            ], sort_keys=True).encode("utf-8"),
        })

    def test_private_zip_roundtrip_durable_cas_receipts_and_audit(self):
        self.assertEqual(_synthetic_preflight(self.payload), ("conversations.json",))
        result = self.ingestor.ingest(
            _stream(self.payload, revision="test-v1"),
            IngestPolicy(max_bytes=256 * 1024),
        )
        self.assertEqual(result.status, IngestStatus.ACCEPTED)
        self.assertIsNotNone(result.raw_artifact)
        self.assertEqual(result.raw_artifact.sha256, hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(result.raw_artifact.size_bytes, len(self.payload))

        reopened = FileSystemStore(self.root)
        self.assertEqual(reopened.read_blob_bytes(result.raw_artifact), self.payload)
        record = reopened.get_record(result.ingest_id)
        self.assertEqual(record["status"], "ACCEPTED")
        self.assertEqual(record["source"]["source_identity"]["claimed_revision"], "test-v1")
        self.assertTrue(any(
            reopened.get_receipt(receipt_id)["stage"] == "acquire"
            for receipt_id in result.receipt_ids
        ))
        audit = reopened.audit_store()
        self.assertEqual(audit["status"], "PASS", audit)

    def test_identical_submission_is_duplicate_but_new_claimed_revision_is_not(self):
        first = self.ingestor.ingest(_stream(self.payload, revision="test-v1"))
        second = self.ingestor.ingest(_stream(self.payload, revision="test-v1"))
        revised = self.ingestor.ingest(_stream(self.payload, revision="test-v2"))
        self.assertEqual(first.status, IngestStatus.ACCEPTED)
        self.assertEqual(second.status, IngestStatus.DUPLICATE)
        self.assertEqual(first.ingest_id, second.ingest_id)
        self.assertEqual(revised.status, IngestStatus.ACCEPTED)
        self.assertNotEqual(first.ingest_id, revised.ingest_id)
        self.assertEqual(first.raw_artifact.sha256, revised.raw_artifact.sha256)

    def test_same_claimed_revision_different_bytes_is_not_remote_version_proof(self):
        other = _synthetic_zip({"conversations.json": b"[]"})
        first = self.ingestor.ingest(_stream(self.payload, revision="same-claim"))
        second = self.ingestor.ingest(_stream(other, revision="same-claim"))
        self.assertEqual((first.status, second.status), (IngestStatus.ACCEPTED, IngestStatus.ACCEPTED))
        self.assertNotEqual(first.ingest_id, second.ingest_id)
        self.assertNotEqual(first.raw_artifact.sha256, second.raw_artifact.sha256)
        # The adapter trusts caller-supplied source_identity. An upstream
        # provider/version-conditional acquisition gate is still required.

    def test_traversal_member_is_held_by_test_preflight_not_by_core_ingest(self):
        malicious = _synthetic_zip({"../outside.txt": b"should-never-extract"})
        with self.assertRaisesRegex(ValueError, "unsafe member path"):
            _synthetic_preflight(malicious)
        raw_only = self.ingestor.ingest(_stream(malicious, revision="test-unsafe"))
        self.assertEqual(raw_only.status, IngestStatus.ACCEPTED)
        self.assertFalse((self.root.parent / "outside.txt").exists())
        self.assertEqual(self.store.read_blob_bytes(raw_only.raw_artifact), malicious)

    def test_malformed_zip_rejected_by_preflight_but_opaque_core_remains_bounded(self):
        malformed = b"not-a-ZIP\x00"
        with self.assertRaisesRegex(ValueError, "invalid ZIP"):
            _synthetic_preflight(malformed)
        raw_only = self.ingestor.ingest(_stream(malformed, revision="test-malformed"))
        self.assertEqual(raw_only.status, IngestStatus.ACCEPTED)
        self.assertEqual(self.store.read_blob_bytes(raw_only.raw_artifact), malformed)

    def test_partial_stream_failure_publishes_no_completed_raw_blob(self):
        def interrupted():
            yield self.payload[:50]
            raise IOError("upstream cut off")

        result = self.ingestor.ingest(StreamSource(
            interrupted(), locator="synthetic:interrupted", media_type="application/zip"
        ))
        self.assertEqual(result.status, IngestStatus.FAILED)
        self.assertIn("caller stream failed", result.error)
        blobs = self.root / "blobs"
        published = [] if not blobs.exists() else [
            item for item in blobs.rglob("*") if item.is_file()
        ]
        self.assertEqual(published, [])

    def test_hard_max_bytes_rejects_before_raw_publication(self):
        result = self.ingestor.ingest(
            _stream(self.payload, revision="test-over-limit"),
            IngestPolicy(max_bytes=len(self.payload) - 1),
        )
        self.assertEqual(result.status, IngestStatus.REJECTED)
        self.assertEqual(result.raw_artifact, None)
        blobs = self.root / "blobs"
        published = [] if not blobs.exists() else [
            item for item in blobs.rglob("*") if item.is_file()
        ]
        self.assertEqual(published, [])


if __name__ == "__main__":
    unittest.main()
