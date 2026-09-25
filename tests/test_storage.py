import os
import tempfile
import unittest
from pathlib import Path

from ingest.storage import FileSystemStore


class RecordingStore(FileSystemStore):
    def __init__(self, root):
        super().__init__(root)
        self.synced_directories = []

    def _fsync_directory(self, path):
        self.synced_directories.append(Path(path))
        return True


class StorageDurabilityTests(unittest.TestCase):
    def test_new_immutable_publication_syncs_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = RecordingStore(root)

            created = store.put_record("record-1", {"schema": "TEST", "value": 1})

            self.assertTrue(created)
            self.assertEqual(
                store.synced_directories,
                [root / "records"],
            )

    @unittest.skipIf(os.name == "nt", "directory fsync is not portable on Windows")
    def test_posix_directory_sync_succeeds_on_real_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(FileSystemStore._fsync_directory(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
