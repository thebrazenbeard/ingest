import math
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

from ingest import (
    BytesSource,
    FileSystemStore,
    GitHubFileSource,
    IngestPolicy,
    IngestStatus,
    Ingestor,
    MessageSource,
    TextSource,
    UrlSource,
)
from ingest.adapters import GitHubAdapter, HttpAdapter
from ingest.canonical import canonical_json


class InvalidJsonGitHubTransport:
    def resolve_ref(self, owner, repository, ref):
        return "a" * 40

    def fetch_file(self, owner, repository, commit, path, max_bytes):
        return b'{"broken":', None, {"git_blob_sha": "b" * 40, "size": 10}


class BarrierStore(FileSystemStore):
    def __init__(self, root):
        super().__init__(root)
        self.barrier = threading.Barrier(2)

    def has_record(self, ingest_id):
        exists = super().has_record(ingest_id)
        if not exists:
            self.barrier.wait(timeout=5)
        return exists


class FakeResponse:
    status = 200
    headers = {"Content-Type": "text/plain"}

    def __init__(self, url):
        self._url = url

    def read(self, _limit):
        return b"hello"

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeOpener:
    def open(self, request, timeout):
        return FakeResponse(request.full_url)


class EvidenceIntegrityTests(unittest.TestCase):
    def test_repeated_quarantine_never_becomes_successful_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingestor = Ingestor(FileSystemStore(Path(tmp) / ".ingest"))
            source = BytesSource(
                b'{"broken":',
                locator="urn:bad-json",
                media_type="application/json",
            )
            first = ingestor.ingest(source)
            second = ingestor.ingest(source)
            self.assertEqual(first.status, IngestStatus.QUARANTINED)
            self.assertEqual(second.status, IngestStatus.QUARANTINED)
            self.assertEqual(first.ingest_id, second.ingest_id)
            self.assertIn("duplicate_existing_record", second.warnings)

    def test_canonical_json_rejects_non_json_and_non_finite_values(self):
        with self.assertRaises((TypeError, ValueError)):
            canonical_json({"value": object()})
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonical_json({"value": value})

    def test_relative_allowed_root_is_rejected_as_ambiguous_policy_identity(self):
        with self.assertRaises(ValueError):
            IngestPolicy(allowed_roots=("relative-root",)).validate()

    def test_github_path_drives_structured_media_type_when_transport_has_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingestor = Ingestor(
                FileSystemStore(Path(tmp) / ".ingest"),
                adapters=[GitHubAdapter(InvalidJsonGitHubTransport())],
            )
            result = ingestor.ingest(
                GitHubFileSource("owner", "repo", "main", "bad.json")
            )
            self.assertEqual(result.status, IngestStatus.QUARANTINED)

    def test_http_source_provenance_does_not_persist_plaintext_url_secrets(self):
        url = "https://user:pass@example.com/path?token=secret&x=1"
        adapter = HttpAdapter(opener=FakeOpener())
        with patch("ingest.adapters.http._host_is_forbidden", return_value=False):
            acquisition = adapter.acquire(UrlSource(url), IngestPolicy())
        serialized = repr(acquisition.source.to_dict())
        for secret in ("user", "pass", "secret"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)
        self.assertEqual(urlparse(acquisition.source.locator).query, "")

    def test_nonfinite_json_is_quarantined_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingestor = Ingestor(FileSystemStore(Path(tmp) / ".ingest"))
            for payload in (b'{"value":NaN}', b'{"value":1e400}'):
                with self.subTest(payload=payload):
                    result = ingestor.ingest(
                        BytesSource(
                            payload,
                            locator=f"urn:nonfinite:{payload!r}",
                            media_type="application/json",
                        )
                    )
                    self.assertEqual(result.status, IngestStatus.QUARANTINED)

    def test_non_json_message_payload_is_rejected_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Ingestor(FileSystemStore(Path(tmp) / ".ingest")).ingest(
                MessageSource("m1", {"bad": object()})
            )
            self.assertEqual(result.status, IngestStatus.REJECTED)

    def test_concurrent_same_ingest_is_accepted_once_then_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BarrierStore(Path(tmp) / ".ingest")
            ingestor = Ingestor(store)
            source = BytesSource(
                b'{"b":2,"a":1}',
                locator="urn:race",
                media_type="application/json",
            )
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(ingestor.ingest, source) for _ in range(2)]
                results = [future.result() for future in futures]
            self.assertEqual(
                sorted(result.status.value for result in results),
                ["ACCEPTED", "DUPLICATE"],
            )
            self.assertEqual(results[0].ingest_id, results[1].ingest_id)


if __name__ == "__main__":
    unittest.main()
