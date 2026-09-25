import hashlib
import math
import os
import tempfile
import time
import unittest
from pathlib import Path

from ingest import Ingestor, TextSource
from ingest.canonical import canonical_json
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

    @unittest.skipIf(os.name == "nt", "directory fsync is not portable on Windows")
    def test_posix_directory_sync_succeeds_on_real_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(FileSystemStore._fsync_directory(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
