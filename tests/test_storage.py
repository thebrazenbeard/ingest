import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from ingest.storage import FileSystemStore


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

    @unittest.skipIf(os.name == "nt", "directory fsync is not portable on Windows")
    def test_posix_directory_sync_succeeds_on_real_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(FileSystemStore._fsync_directory(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
