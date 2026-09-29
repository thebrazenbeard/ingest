import json
import tempfile
import unittest
from pathlib import Path

from ingest import FileSystemStore, Ingestor, TextSource


ROOT = Path(__file__).resolve().parents[1]


class SchemaSurfaceTests(unittest.TestCase):
    def test_schema_contracts_and_emitted_shapes_agree_on_required_keys(self):
        record_schema = json.loads((ROOT / "schemas/ingest-record-v1.schema.json").read_text())
        receipt_schema = json.loads((ROOT / "schemas/ingest-stage-receipt-v1.schema.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store).ingest(TextSource("schema", locator="urn:schema"))
            record = store.get_record(result.ingest_id)
            receipt = store.get_receipt(result.receipt_ids[0])
        self.assertEqual(record_schema["$id"], record["schema"])
        self.assertEqual(receipt_schema["$id"], receipt["schema"])
        self.assertTrue(set(record_schema["required"]).issubset(record))
        self.assertTrue(set(receipt_schema["required"]).issubset(receipt))

    def test_record_audit_schema_matches_clean_and_corrupt_outputs(self):
        schema = json.loads(
            (ROOT / "schemas/ingest-record-audit-v1.schema.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            result = Ingestor(store).ingest(
                TextSource("record audit", locator="urn:schema:record-audit")
            )
            clean = store.audit_records()
            (root / result.raw_artifact.storage_locator).write_bytes(b"broken")
            corrupt = store.audit_records()

        self.assertEqual(schema["$id"], "INGEST_RECORD_AUDIT_V1")
        self.assertEqual(schema["properties"]["schema"]["const"], schema["$id"])
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]),
            {"PASS", "CORRUPT"},
        )
        for payload in (clean, corrupt):
            self.assertEqual(payload["schema"], schema["$id"])
            self.assertTrue(set(schema["required"]).issubset(payload))
        self.assertEqual(clean["status"], "PASS")
        self.assertEqual(corrupt["status"], "CORRUPT")
        self.assertTrue(corrupt["issues"])
        self.assertTrue(
            set(schema["$defs"]["issue"]["required"]).issubset(
                corrupt["issues"][0]
            )
        )

    def test_store_audit_schema_matches_pass_issues_and_corrupt_outputs(self):
        schema = json.loads(
            (ROOT / "schemas/ingest-store-audit-v1.schema.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".ingest"
            store = FileSystemStore(root)
            clean_result = Ingestor(store).ingest(
                TextSource("store audit", locator="urn:schema:store-audit")
            )
            clean = store.audit_store()
            orphan, _created = store.put_blob(
                b"orphan",
                media_type="application/octet-stream",
                kind="raw",
            )
            issues = store.audit_store()
            (root / clean_result.raw_artifact.storage_locator).write_bytes(
                b"broken"
            )
            corrupt = store.audit_store()

        self.assertEqual(schema["$id"], "INGEST_STORE_AUDIT_V1")
        self.assertEqual(schema["properties"]["schema"]["const"], schema["$id"])
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]),
            {"PASS", "ISSUES", "CORRUPT"},
        )
        for payload in (clean, issues, corrupt):
            self.assertEqual(payload["schema"], schema["$id"])
            self.assertTrue(set(schema["required"]).issubset(payload))
            self.assertTrue(
                set(schema["$defs"]["inventory"]["required"]).issubset(
                    payload["inventory"]
                )
            )
        self.assertEqual(clean["status"], "PASS")
        self.assertEqual(issues["status"], "ISSUES")
        self.assertIn(orphan.artifact_id, issues["unreferenced_blobs"])
        self.assertEqual(corrupt["status"], "CORRUPT")
        self.assertTrue(corrupt["issues"])
        self.assertTrue(
            set(schema["$defs"]["issue"]["required"]).issubset(
                corrupt["issues"][0]
            )
        )


if __name__ == "__main__":
    unittest.main()
