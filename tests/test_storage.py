import hashlib
import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ingest import Ingestor, TextSource
from ingest.canonical import canonical_digest, canonical_json
from ingest.storage import FileSystemStore, StoreConflict, StoreIntegrityError


class RecordingStore(FileSystemStore):
    def __init__(self, root):
        self.synced_directories = []
        super().__init__(root)
        self.synced_directories.clear()

    def _fsync_directory(self, path):
        self.synced_directories.append(Path(path))
        return True


class ConstructorRecordingStore(FileSystemStore):
    def __init__(self, root):
        self.synced_directories = []
        super().__init__(root)

    def _fsync_directory(self, path):
        self.synced_directories.append(Path(path))
        return True


class StorageDurabilityTests(unittest.TestCase):
    def test_new_store_root_syncs_its_parent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / ".ingest"

            store = ConstructorRecordingStore(root)

            self.assertTrue(root.is_dir())
            self.assertEqual(store.synced_directories, [parent])

    def test_new_immutable_publication_syncs_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = RecordingStore(root)

            created = store.put_record("record-1", {"schema": "TEST", "value": 1})

            self.assertTrue(created)
            self.assertEqual(
                store.synced_directories,
                [
                    root,
                    root / "records",
                ],
            )

    def test_new_directory_chain_syncs_each_parent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = RecordingStore(root)
            data = b"directory-chain"
            prefix = hashlib.sha256(data).hexdigest()[:2]

            _artifact, created = store.put_blob(
                data,
                media_type="application/octet-stream",
                kind="raw",
            )

            self.assertTrue(created)
            self.assertEqual(
                store.synced_directories,
                [
                    root,
                    root / "blobs",
                    root / "blobs" / "sha256",
                    root / "blobs" / "sha256" / prefix,
                ],
            )

    def test_managed_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            outside = Path(tmp) / "outside"
            outside.mkdir()
            store = FileSystemStore(root)
            (root / "records").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(StoreConflict):
                store.put_record("record-1", {"schema": "TEST", "value": 1})

            self.assertFalse((outside / "record-1.json").exists())

    def test_final_immutable_symlink_is_not_accepted_as_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            value = {"schema": "TEST", "value": 1}
            self.assertTrue(store.put_record("record-1", value))
            record_path = root / "records" / "record-1.json"
            outside = Path(tmp) / "outside-record.json"
            outside.write_bytes(record_path.read_bytes())
            record_path.unlink()
            record_path.symlink_to(outside)

            with self.assertRaises(StoreConflict):
                store.put_record("record-1", value)

    def test_cleanup_stale_temp_files_reclaims_only_old_owned_temps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = RecordingStore(root)
            records = root / "records"
            records.mkdir()
            old_temp = records / ".tmp-old"
            recent_temp = records / ".tmp-recent"
            unrelated = records / "keep.txt"
            old_temp.write_bytes(b"old")
            recent_temp.write_bytes(b"recent")
            unrelated.write_bytes(b"keep")
            now = time.time()
            os.utime(old_temp, (now - 7200, now - 7200))
            os.utime(recent_temp, (now, now))
            store.synced_directories.clear()

            result = store.cleanup_stale_temp_files(older_than_seconds=3600)

            self.assertEqual(
                result,
                {"files_removed": 1, "bytes_removed": 3},
            )
            self.assertFalse(old_temp.exists())
            self.assertTrue(recent_temp.exists())
            self.assertTrue(unrelated.exists())
            self.assertEqual(store.synced_directories, [records])

    def test_tampered_receipt_is_rejected_on_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("receipt integrity", locator="urn:receipt-integrity")
            )
            receipt_id = result.receipt_ids[-1]
            path = store.root / "receipts" / f"{receipt_id}.json"
            payload = store.get_receipt(receipt_id)
            payload["outcome"] = "TAMPERED"
            path.write_bytes((canonical_json(payload) + "\n").encode("utf-8"))

            with self.assertRaises(StoreIntegrityError):
                store.get_receipt(receipt_id)

    def test_record_read_rejects_source_metadata_inconsistent_with_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("source integrity", locator="urn:source-integrity")
            )
            path = store.root / "records" / f"{result.ingest_id}.json"
            payload = store.get_record(result.ingest_id)
            payload["source"]["observed_metadata"]["tampered"] = True
            path.write_bytes((canonical_json(payload) + "\n").encode("utf-8"))

            with self.assertRaises(StoreIntegrityError):
                store.get_record(result.ingest_id)

    def test_put_derived_blob_stream_is_normalized_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            artifact, created = store.put_derived_blob_stream(
                [b"derived"],
                media_type="text/plain",
            )

            self.assertTrue(created)
            self.assertEqual(artifact.kind, "normalized")

            with self.assertRaises(TypeError):
                store.put_derived_blob_stream(
                    [b"not-allowed"],
                    media_type="application/octet-stream",
                    kind="raw",
                )

    def test_put_blob_stream_publishes_exact_bytes_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            chunks = [b"alpha", b"", b"beta", b"gamma"]
            expected = b"alphabetagamma"

            artifact, created = store.put_blob_stream(
                iter(chunks),
                media_type="application/octet-stream",
                kind="raw",
                max_bytes=1024,
            )

            self.assertTrue(created)
            self.assertEqual(artifact.size_bytes, len(expected))
            self.assertEqual(
                artifact.sha256,
                hashlib.sha256(expected).hexdigest(),
            )
            self.assertEqual(
                (store.root / artifact.storage_locator).read_bytes(),
                expected,
            )

            repeated, created = store.put_blob_stream(
                (chunk for chunk in chunks),
                media_type="application/octet-stream",
                kind="raw",
                max_bytes=1024,
            )

            self.assertFalse(created)
            self.assertEqual(repeated.artifact_id, artifact.artifact_id)

    def test_put_blob_stream_rejects_over_limit_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)

            with self.assertRaises(ValueError):
                store.put_blob_stream(
                    [b"abc", b"def"],
                    media_type="application/octet-stream",
                    kind="raw",
                    max_bytes=5,
                )

            blob_root = root / "blobs"
            remaining_files = (
                []
                if not blob_root.exists()
                else [
                    path
                    for path in blob_root.rglob("*")
                    if path.is_file()
                ]
            )
            self.assertEqual(remaining_files, [])

    def test_repeated_blob_publication_ignores_ctime_only_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            data = b"stable-content"
            artifact, created = store.put_blob(
                data,
                media_type="application/octet-stream",
                kind="raw",
            )
            self.assertTrue(created)
            real_fstat = os.fstat
            calls = 0

            def drift_ctime(fd):
                nonlocal calls
                value = real_fstat(fd)
                calls += 1
                return SimpleNamespace(
                    st_dev=value.st_dev,
                    st_ino=value.st_ino,
                    st_size=value.st_size,
                    st_mtime_ns=value.st_mtime_ns,
                    st_ctime_ns=value.st_ctime_ns + calls,
                )

            with patch(
                "ingest.storage.os.fstat",
                side_effect=drift_ctime,
            ):
                repeated, created = store.put_blob(
                    data,
                    media_type="application/octet-stream",
                    kind="raw",
                )

            self.assertFalse(created)
            self.assertEqual(repeated.artifact_id, artifact.artifact_id)

    def test_iter_blob_chunks_verifies_exact_published_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            data = b"abcdefghijklmnopqrstuvwxyz"
            artifact, _created = store.put_blob(
                data,
                media_type="application/octet-stream",
                kind="raw",
            )

            chunks = list(store.iter_blob_chunks(artifact, chunk_size=5))

            self.assertEqual(b"".join(chunks), data)
            self.assertTrue(all(0 < len(chunk) <= 5 for chunk in chunks))

            (store.root / artifact.storage_locator).write_bytes(b"corrupted")
            with self.assertRaises(StoreIntegrityError):
                b"".join(store.iter_blob_chunks(artifact, chunk_size=5))

    def test_iter_blob_chunks_rejects_invalid_chunk_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            artifact, _created = store.put_blob(
                b"x",
                media_type="application/octet-stream",
                kind="raw",
            )

            with self.assertRaises(ValueError):
                list(store.iter_blob_chunks(artifact, chunk_size=0))

    def test_repeated_blob_publication_does_not_materialize_existing_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            data = b"x" * (256 * 1024)
            artifact, created = store.put_blob(
                data,
                media_type="application/octet-stream",
                kind="raw",
            )
            self.assertTrue(created)
            blob_path = store.root / artifact.storage_locator
            original_read_bytes = Path.read_bytes

            def reject_blob_read_bytes(path):
                if path == blob_path:
                    raise AssertionError(
                        "immutable collision check materialized existing blob"
                    )
                return original_read_bytes(path)

            with patch.object(Path, "read_bytes", reject_blob_read_bytes):
                repeated, created = store.put_blob(
                    data,
                    media_type="application/octet-stream",
                    kind="raw",
                )

            self.assertFalse(created)
            self.assertEqual(repeated.artifact_id, artifact.artifact_id)

    def test_record_verification_hashes_artifacts_without_materializing_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("x" * (256 * 1024), locator="urn:stream-verify")
            )
            original_read = store._read_managed_bytes

            def reject_blob_materialization(path, *, expected_size=None):
                if "blobs" in Path(path).parts:
                    raise AssertionError(
                        "artifact verification materialized blob bytes"
                    )
                return original_read(path, expected_size=expected_size)

            with patch.object(
                store,
                "_read_managed_bytes",
                side_effect=reject_blob_materialization,
            ):
                record = store.get_record(result.ingest_id)

            self.assertEqual(record["ingest_id"], result.ingest_id)

    def test_artifact_size_mismatch_is_rejected_before_blob_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            artifact, _created = store.put_blob(
                b"small",
                media_type="application/octet-stream",
                kind="raw",
            )
            blob_path = store.root / artifact.storage_locator
            blob_path.write_bytes(b"larger-than-declared")

            with patch(
                "ingest.storage.os.read",
                side_effect=AssertionError("blob bytes should not be read"),
            ):
                with self.assertRaises(StoreIntegrityError):
                    store._verify_artifact(
                        artifact.to_dict(),
                        expected_kind="raw",
                    )

    def test_record_read_rejects_corrupted_referenced_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("blob integrity", locator="urn:blob-integrity")
            )
            blob_path = store.root / result.raw_artifact.storage_locator
            blob_path.write_bytes(b"corrupted")

            with self.assertRaises(StoreIntegrityError):
                store.get_record(result.ingest_id)

    def test_derivation_rejects_self_digested_but_wrong_stage_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("hello\r\nworld", locator="urn:derivation-stage")
            )
            derivation_id = result.derivation_ids[0]
            derivation = store.get_derivation(derivation_id)
            receipt_id = derivation["receipt_id"]
            receipt_path = store.root / "receipts" / f"{receipt_id}.json"
            receipt = store.get_receipt(receipt_id)
            receipt["stage"] = "acquire"
            body = dict(receipt)
            body.pop("receipt_digest")
            receipt["receipt_digest"] = canonical_digest(body)
            receipt_path.write_bytes(
                (canonical_json(receipt) + "\n").encode("utf-8")
            )

            with self.assertRaises(StoreIntegrityError):
                store.get_derivation(derivation_id)

    def test_record_rejects_derivation_receipt_from_foreign_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            first = Ingestor(store).ingest(
                TextSource("first\r\nvalue", locator="urn:derivation-first")
            )
            second = Ingestor(store).ingest(
                TextSource("second\r\nvalue", locator="urn:derivation-second")
            )
            derivation_id = first.derivation_ids[0]
            derivation_path = (
                store.root / "derivations" / f"{derivation_id}.json"
            )
            derivation = store.get_derivation(derivation_id)
            second_record = store.get_record(second.ingest_id)
            second_normalize_receipt = next(
                receipt_id
                for receipt_id in second_record["receipt_ids"]
                if store.get_receipt(receipt_id)["stage"] == "normalize"
            )
            derivation["receipt_id"] = second_normalize_receipt
            derivation_path.write_bytes(
                (canonical_json(derivation) + "\n").encode("utf-8")
            )

            with self.assertRaises(StoreIntegrityError):
                store.get_record(first.ingest_id)

    def test_record_accepts_equivalent_derivation_receipt_from_same_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("same\r\ningest", locator="urn:same-ingest-receipt")
            )
            derivation_id = result.derivation_ids[0]
            derivation_path = (
                store.root / "derivations" / f"{derivation_id}.json"
            )
            derivation = store.get_derivation(derivation_id)
            original_receipt = store.get_receipt(derivation["receipt_id"])
            alternate_receipt = dict(original_receipt)
            alternate_receipt["receipt_id"] = "r_same_ingest_alternate"
            body = dict(alternate_receipt)
            body.pop("receipt_digest")
            alternate_receipt["receipt_digest"] = canonical_digest(body)
            store.put_receipt(
                alternate_receipt["receipt_id"],
                alternate_receipt,
            )
            derivation["receipt_id"] = alternate_receipt["receipt_id"]
            derivation_path.write_bytes(
                (canonical_json(derivation) + "\n").encode("utf-8")
            )

            record = store.get_record(result.ingest_id)

            self.assertEqual(record["ingest_id"], result.ingest_id)
            self.assertNotIn(
                alternate_receipt["receipt_id"],
                record["receipt_ids"],
            )

    def test_derivation_read_rejects_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(
                TextSource("hello\r\nworld", locator="urn:derivation-integrity")
            )
            self.assertTrue(result.derivation_ids)
            derivation_id = result.derivation_ids[0]
            path = store.root / "derivations" / f"{derivation_id}.json"
            payload = store.get_derivation(derivation_id)
            payload["relation"] = "TAMPERED_RELATION"
            path.write_bytes((canonical_json(payload) + "\n").encode("utf-8"))

            with self.assertRaises(StoreIntegrityError):
                store.get_derivation(derivation_id)

    def test_cleanup_stale_temp_files_rejects_invalid_age_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            for value in (-1.0, math.nan, math.inf):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        store.cleanup_stale_temp_files(
                            older_than_seconds=value,
                        )


    def test_audit_records_passes_clean_record_graphs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            Ingestor(store).ingest(TextSource("one", locator="urn:audit:one"))
            Ingestor(store).ingest(TextSource("two", locator="urn:audit:two"))

            report = store.audit_records()

            self.assertEqual(report["schema"], "INGEST_RECORD_AUDIT_V1")
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["records_checked"], 2)
            self.assertEqual(report["records_ok"], 2)
            self.assertEqual(report["records_corrupt"], 0)
            self.assertEqual(report["issues"], [])

    def test_audit_records_collects_corruption_without_stopping(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            good = Ingestor(store).ingest(
                TextSource("good", locator="urn:audit:good")
            )
            bad = Ingestor(store).ingest(
                TextSource("bad", locator="urn:audit:bad")
            )
            bad_blob = store.root / bad.raw_artifact.storage_locator
            bad_blob.write_bytes(b"corrupt")

            report = store.audit_records()

            self.assertEqual(report["status"], "CORRUPT")
            self.assertEqual(report["records_checked"], 2)
            self.assertEqual(report["records_ok"], 1)
            self.assertEqual(report["records_corrupt"], 1)
            self.assertEqual(len(report["issues"]), 1)
            self.assertEqual(report["issues"][0]["ingest_id"], bad.ingest_id)
            self.assertNotEqual(good.ingest_id, bad.ingest_id)

    def test_audit_records_flags_unexpected_record_directory_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            records = store.root / "records"
            records.mkdir()
            (records / "not-a-record.tmp").write_bytes(b"junk")

            report = store.audit_records()

            self.assertEqual(report["status"], "CORRUPT")
            self.assertEqual(report["records_checked"], 0)
            self.assertEqual(report["records_corrupt"], 1)
            self.assertEqual(
                report["issues"][0]["entry"],
                "not-a-record.tmp",
            )

    def test_audit_store_passes_clean_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            Ingestor(store).ingest(
                TextSource("clean\r\ninventory", locator="urn:store-audit:clean")
            )

            report = store.audit_store()

            self.assertEqual(report["schema"], "INGEST_STORE_AUDIT_V1")
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["records_checked"], 1)
            self.assertEqual(report["records_corrupt"], 0)
            self.assertEqual(report["unreferenced_blobs"], [])
            self.assertEqual(report["unreferenced_receipts"], [])
            self.assertEqual(report["unreferenced_derivations"], [])
            self.assertEqual(report["stale_temp_files"], [])
            self.assertEqual(report["issues"], [])

    def test_audit_store_reports_unreferenced_objects_and_stale_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            result = Ingestor(store).ingest(
                TextSource("referenced", locator="urn:store-audit:referenced")
            )
            orphan_artifact, _created = store.put_blob(
                b"orphan-blob",
                media_type="application/octet-stream",
                kind="raw",
            )
            receipt = store.get_receipt(result.receipt_ids[0])
            orphan_receipt = dict(receipt)
            orphan_receipt["receipt_id"] = "r_orphan_inventory"
            body = dict(orphan_receipt)
            body.pop("receipt_digest")
            orphan_receipt["receipt_digest"] = canonical_digest(body)
            store.put_receipt(orphan_receipt["receipt_id"], orphan_receipt)

            temp_path = root / "blobs" / "sha256" / ".tmp-stale-audit"
            temp_path.write_bytes(b"stale")
            old = time.time() - 7200
            os.utime(temp_path, (old, old))

            report = store.audit_store(stale_after_seconds=3600)

            self.assertEqual(report["status"], "ISSUES")
            self.assertIn(
                orphan_artifact.artifact_id,
                report["unreferenced_blobs"],
            )
            self.assertIn(
                orphan_receipt["receipt_id"],
                report["unreferenced_receipts"],
            )
            self.assertIn(
                "blobs/sha256/.tmp-stale-audit",
                report["stale_temp_files"],
            )
            self.assertEqual(report["issues"], [])

    def test_audit_store_reports_derivation_unreferenced_by_valid_record_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            result = Ingestor(store).ingest(
                TextSource(
                    "orphan\r\nderivation",
                    locator="urn:store-audit:orphan-derivation",
                )
            )
            self.assertTrue(result.derivation_ids)
            (root / "records" / f"{result.ingest_id}.json").unlink()

            report = store.audit_store()

            self.assertEqual(report["status"], "ISSUES")
            self.assertIn(
                result.derivation_ids[0],
                report["unreferenced_derivations"],
            )
            self.assertTrue(report["unreferenced_receipts"])
            self.assertTrue(report["unreferenced_blobs"])

    def test_audit_store_distinguishes_corruption_from_inventory_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            result = Ingestor(store).ingest(
                TextSource("corrupt", locator="urn:store-audit:corrupt")
            )
            (root / result.raw_artifact.storage_locator).write_bytes(b"broken")
            unexpected = root / "receipts" / "unexpected.txt"
            unexpected.write_text("junk", encoding="utf-8")

            report = store.audit_store()

            self.assertEqual(report["status"], "CORRUPT")
            kinds = {issue["kind"] for issue in report["issues"]}
            self.assertIn("record_corrupt", kinds)
            self.assertIn("unexpected_entry", kinds)

    def test_audit_store_flags_symlinked_sha256_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            outside = Path(tmp) / "outside-blobs"
            outside.mkdir()
            store = FileSystemStore(root)
            (root / "blobs").mkdir()
            (root / "blobs" / "sha256").symlink_to(
                outside,
                target_is_directory=True,
            )

            report = store.audit_store()

            self.assertEqual(report["status"], "CORRUPT")
            self.assertTrue(
                any(
                    issue["kind"] == "unexpected_entry"
                    and issue["entry"] == "blobs/sha256"
                    for issue in report["issues"]
                )
            )

    def test_audit_store_rejects_invalid_stale_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            for value in (-1.0, math.nan, math.inf):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        store.audit_store(stale_after_seconds=value)

    @unittest.skipIf(os.name == "nt", "directory fsync is not portable on Windows")
    def test_posix_directory_sync_succeeds_on_real_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(FileSystemStore._fsync_directory(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
