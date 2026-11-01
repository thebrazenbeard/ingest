"""Synthetic installed-wheel metadata tests for the standalone ownership audit.

These exercise real importlib.metadata parsing of PEP 376 RECORD files rather
than mocking the distribution introspection boundary.
"""

from __future__ import annotations

import base64
import csv
import hashlib
from importlib import metadata
from pathlib import Path
import tempfile
import unittest

from tools.audit_install_ownership import audit_ownership


def _record_hash(content: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")


class InstallOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)

    def _distribution(
        self,
        name: str,
        code: dict[str, bytes] | None,
        *,
        omit_record: bool = False,
        record_override: dict[str, str] | None = None,
        top_level: str = "ingest",
    ) -> None:
        info = self.site / f"{name.replace('-', '_')}-0.1.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 0.1.0\n")
        (info / "top_level.txt").write_text(top_level + "\n")
        if omit_record:
            return
        rows = []
        for path, content in (code or {}).items():
            file = self.site / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
            rows.append((path, (record_override or {}).get(path, _record_hash(content)), len(content)))
        rows.append((str(info.relative_to(self.site) / "RECORD"), "", ""))
        with (info / "RECORD").open("w", newline="") as output:
            csv.writer(output).writerows(rows)

    def _audit(self) -> dict:
        return audit_ownership(metadata.distributions(path=[str(self.site)]))

    def test_single_verified_owner_is_pass(self) -> None:
        self._distribution("vera-ingest", {"ingest/__init__.py": b"canonical\n", "ingest/storage.py": b"standalone\n"})
        result = self._audit()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["owned_files"], 2)
        self.assertEqual(result["foreign_owners"], [])

    def test_pip_generated_pyc_and_console_script_do_not_false_fail(self) -> None:
        self._distribution("vera-ingest", {"ingest/__init__.py": b"canonical"})
        info = self.site / "vera_ingest-0.1.0.dist-info" / "RECORD"
        with info.open("a") as output:
            output.write("ingest/__pycache__/__init__.cpython-312.pyc,,\n")
            output.write("../../../bin/ingest,,\n")
        self.assertEqual(self._audit()["status"], "PASS")

    def test_other_distribution_claims_same_import_path(self) -> None:
        self._distribution("vera-ingest", {"ingest/__init__.py": b"standalone", "ingest/storage.py": b"standalone"})
        self._distribution("vera-mono", {"ingest/__init__.py": b"mono", "ingest/storage.py": b"mono"})
        result = self._audit()
        self.assertEqual(result["status"], "COLLISION", result)
        self.assertEqual(result["foreign_owners"], ["vera-mono"])
        self.assertEqual(result["overlapping_paths"], ["ingest/__init__.py", "ingest/storage.py"])

    def test_disjoint_files_under_same_non_namespace_package_still_collide(self) -> None:
        self._distribution("vera-ingest", {"ingest/__init__.py": b"standalone"})
        self._distribution("unrelated-adapter", {"ingest/extras.py": b"foreign"})
        result = self._audit()
        self.assertEqual(result["status"], "COLLISION", result)
        self.assertEqual(result["overlapping_paths"], [])
        self.assertEqual(result["foreign_owners"], ["unrelated-adapter"])

    def test_installed_file_changed_since_record_is_not_pass(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"original"})
        (self.site / "ingest/storage.py").write_bytes(b"overwritten")
        result = self._audit()
        self.assertEqual(result["status"], "INTEGRITY_FAILURE", result)
        self.assertEqual(result["invalid_files"], ["ingest/storage.py"])

    def test_missing_owned_file_after_uninstall_is_not_pass(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"original"})
        (self.site / "ingest/storage.py").unlink()
        result = self._audit()
        self.assertEqual(result["status"], "INTEGRITY_FAILURE", result)

    def test_missing_record_prevents_green(self) -> None:
        self._distribution("vera-ingest", None, omit_record=True)
        result = self._audit()
        self.assertEqual(result["status"], "UNKNOWN", result)

    def test_missing_record_foreign_top_level_owner_prevents_green(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"owned"})
        self._distribution("possible-owner", None, omit_record=True)
        result = self._audit()
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertIn("possible-owner", result["unverified_owners"])

    def test_foreign_top_level_claim_with_record_without_source_prevents_green(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"owned"})
        self._distribution("editable-candidate", {"other/__init__.py": b"not-an-ingest-record"},
                           top_level="ingest")
        result = self._audit()
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertIn("editable-candidate", result["unverified_owners"])

    def test_missing_digest_and_malformed_hash_prevent_green(self) -> None:
        for bad in ("", "sha256=wrong", "sha512=abc"):
            with self.subTest(bad=bad):
                with tempfile.TemporaryDirectory() as scratch:
                    self.site = Path(scratch)
                    self._distribution("vera-ingest", {"ingest/storage.py": b"owned"}, record_override={"ingest/storage.py": bad})
                    self.assertEqual(self._audit()["status"], "INTEGRITY_FAILURE")

    def test_record_path_traversal_is_not_verified(self) -> None:
        self._distribution("vera-ingest", {"ingest/../outside.py": b"unsafe"})
        result = self._audit()
        self.assertEqual(result["status"], "UNKNOWN", result)

    def test_windows_casefold_foreign_claim_cannot_be_ignored(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"owned"})
        self._distribution("foreign-case", {"INGEST/storage.py": b"foreign"})
        result = self._audit()
        self.assertNotEqual(result["status"], "PASS", result)
        self.assertIn("foreign-case", result["unverified_owners"])

    def test_noncanonical_aliases_do_not_receive_verified_ownership(self) -> None:
        for alias in ("ingest//alias.py", "./ingest/alias.py", "ingest/./alias.py"):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as scratch:
                self.site = Path(scratch)
                self._distribution("vera-ingest", {alias: b"owned"})
                result = self._audit()
                self.assertEqual(result["status"], "UNKNOWN", result)

    def test_foreign_sourceless_bytecode_is_not_silently_ignored(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"owned"})
        self._distribution("foreign-bytecode", {"ingest/rogue.pyc": b"bytecode"})
        result = self._audit()
        self.assertNotEqual(result["status"], "PASS", result)

    def test_foreign_cached_bytecode_is_not_silently_ignored(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"owned"})
        self._distribution("foreign-cache", {"ingest/__pycache__/storage.cpython-312.pyc": b"foreign-cache"})
        result = self._audit()
        self.assertEqual(result["status"], "COLLISION", result)

    def test_symlinked_package_root_outside_site_cannot_be_verified(self) -> None:
        self._distribution("vera-ingest", {"ingest/storage.py": b"owned"})
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        external_root = Path(external.name)
        (external_root / "storage.py").write_bytes(b"owned")
        package_root = self.site / "ingest"
        package_root.rename(self.site / "prelink_ingest")
        try:
            package_root.symlink_to(external_root, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        result = self._audit()
        self.assertEqual(result["status"], "INTEGRITY_FAILURE", result)

    def test_traversal_through_pycache_is_not_silently_ignored(self) -> None:
        self._distribution("vera-ingest", {
            "ingest/storage.py": b"owned",
            "ingest/../__pycache__/payload.py": b"unsafe",
        })
        result = self._audit()
        self.assertEqual(result["status"], "UNKNOWN", result)

    def test_no_standalone_distribution_is_not_installed(self) -> None:
        self._distribution("vera-mono", {"ingest/storage.py": b"mono"})
        self.assertEqual(self._audit()["status"], "NOT_INSTALLED")


if __name__ == "__main__":
    unittest.main()
