import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingest import (
    BytesSource,
    FileSource,
    FileSystemStore,
    GitHubFileSource,
    IngestPolicy,
    IngestStatus,
    Ingestor,
    MessageSource,
)
from ingest.adapters import FileAdapter, GitHubAdapter, MessageAdapter, TextBytesAdapter


class FakeGitHubTransport:
    def resolve_ref(self, owner, repository, ref):
        self.resolve_args = (owner, repository, ref)
        return "a" * 40

    def fetch_file(self, owner, repository, commit, path, max_bytes):
        self.fetch_args = (owner, repository, commit, path, max_bytes)
        return b"hello from github\n", "text/plain", {"git_blob_sha": "b" * 40, "size": 18}


class FakeStreamingGitHubTransport:
    def resolve_ref(self, owner, repository, ref):
        self.resolve_args = (owner, repository, ref)
        return "a" * 40

    def fetch_file_stream(
        self,
        owner,
        repository,
        commit,
        path,
        max_bytes,
    ):
        self.fetch_args = (
            owner,
            repository,
            commit,
            path,
            max_bytes,
        )
        data = b"hello from streamed github\n"
        return (
            iter([data[:7], data[7:]]),
            None,
            {"git_blob_sha": "b" * 40, "size": len(data)},
        )

    def fetch_file(self, *_args, **_kwargs):
        raise AssertionError("buffered GitHub fetch should not be used")


class AdapterPolicyTests(unittest.TestCase):
    def test_parser_driving_media_type_is_part_of_ingest_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingestor = Ingestor(FileSystemStore(Path(tmp) / ".ingest"), adapters=[TextBytesAdapter()])
            text = ingestor.ingest(BytesSource(b'{"a":1}', locator="urn:same", media_type="text/plain"))
            structured = ingestor.ingest(BytesSource(b'{"a":1}', locator="urn:same", media_type="application/json"))
            self.assertEqual(text.status, IngestStatus.ACCEPTED)
            self.assertEqual(structured.status, IngestStatus.ACCEPTED)
            self.assertNotEqual(text.ingest_id, structured.ingest_id)

    def test_file_root_confinement_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "allowed"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("nope", encoding="utf-8")
            ingestor = Ingestor(FileSystemStore(Path(tmp) / ".ingest"), adapters=[FileAdapter()])
            result = ingestor.ingest(
                FileSource(str(outside)),
                IngestPolicy(allowed_roots=(str(root),)),
            )
            self.assertEqual(result.status, IngestStatus.REJECTED)
            self.assertIn("outside allowed_roots", result.error)

    def test_ingestor_streams_file_capture_instead_of_buffered_adapter_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "streamed.txt"
            path.write_text("hello\r\nworld", encoding="utf-8")
            store = FileSystemStore(Path(tmp) / ".ingest")
            adapter = FileAdapter()

            with patch.object(
                adapter,
                "acquire",
                side_effect=AssertionError(
                    "buffered FileAdapter.acquire should not be used"
                ),
            ), patch.object(
                store,
                "put_blob_stream",
                wraps=store.put_blob_stream,
            ) as stream_put:
                result = Ingestor(
                    store,
                    adapters=[adapter],
                ).ingest(FileSource(str(path)))

            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            stream_put.assert_called_once()
            self.assertEqual(
                (store.root / result.raw_artifact.storage_locator).read_bytes(),
                b"hello\r\nworld",
            )

    def test_streaming_file_change_during_capture_is_failed_without_raw_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changing.bin"
            path.write_bytes(b"a" * (128 * 1024))
            store = FileSystemStore(Path(tmp) / ".ingest")
            adapter = FileAdapter()
            original_read = os.read
            original_stat = path.stat()
            changed = False

            def read_then_touch(fd, size):
                nonlocal changed
                chunk = original_read(fd, size)
                if chunk and not changed:
                    changed = True
                    os.utime(
                        path,
                        ns=(
                            original_stat.st_atime_ns,
                            original_stat.st_mtime_ns + 1_000_000_000,
                        ),
                    )
                return chunk

            with patch(
                "ingest.adapters.file.os.read",
                side_effect=read_then_touch,
            ):
                result = Ingestor(
                    store,
                    adapters=[adapter],
                ).ingest(FileSource(str(path)))

            self.assertEqual(result.status, IngestStatus.FAILED)
            self.assertIn("changed during acquisition", result.error)
            blob_root = store.root / "blobs"
            blob_files = (
                []
                if not blob_root.exists()
                else [
                    item
                    for item in blob_root.rglob("*")
                    if item.is_file()
                ]
            )
            self.assertEqual(blob_files, [])

    def test_opaque_streamed_file_skips_post_capture_blob_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opaque.bin"
            path.write_bytes(b"plain utf8 bytes in a binary-named file")
            store = FileSystemStore(Path(tmp) / ".ingest")

            with patch.object(
                store,
                "read_blob_bytes",
                side_effect=AssertionError(
                    "opaque streamed file should not be materialized"
                ),
            ):
                result = Ingestor(
                    store,
                    adapters=[FileAdapter()],
                ).ingest(FileSource(str(path)))

            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            self.assertIsNone(result.normalized_artifact)
            self.assertEqual(result.raw_artifact.media_type, "text/plain")
            self.assertIn(
                "media_type_mismatch: "
                "claimed=application/octet-stream sniffed=text/plain",
                result.warnings,
            )

    def test_json_candidate_stream_still_materializes_for_exact_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.bin"
            path.write_bytes(b'{"a":1}')
            store = FileSystemStore(Path(tmp) / ".ingest")

            with patch.object(
                store,
                "read_blob_bytes",
                wraps=store.read_blob_bytes,
            ) as read_blob:
                result = Ingestor(
                    store,
                    adapters=[FileAdapter()],
                ).ingest(FileSource(str(path)))

            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            self.assertEqual(result.raw_artifact.media_type, "application/json")
            self.assertIsNone(result.normalized_artifact)
            self.assertGreaterEqual(read_blob.call_count, 1)

    def test_invalid_json_file_is_quarantined_but_raw_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"broken":', encoding="utf-8")
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store, adapters=[FileAdapter()]).ingest(FileSource(str(path)))
            self.assertEqual(result.status, IngestStatus.QUARANTINED)
            self.assertIsNotNone(result.raw_artifact)
            self.assertTrue((store.root / result.raw_artifact.storage_locator).is_file())

    def test_jsonl_file_is_canonicalized_line_by_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"b":2,"a":1}\n\n{"z":0}\n', encoding="utf-8")
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(store, adapters=[FileAdapter()]).ingest(FileSource(str(path)))
            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            self.assertIsNotNone(result.normalized_artifact)
            normalized = (store.root / result.normalized_artifact.storage_locator).read_bytes()
            self.assertEqual(normalized, b'{"a":1,"b":2}\n{"z":0}\n')

    def test_ingestor_streams_github_when_transport_supports_streaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeStreamingGitHubTransport()
            adapter = GitHubAdapter(transport)
            store = FileSystemStore(Path(tmp) / ".ingest")

            with patch.object(
                adapter,
                "acquire",
                side_effect=AssertionError(
                    "buffered GitHubAdapter.acquire should not be used"
                ),
            ), patch.object(
                store,
                "put_blob_stream",
                wraps=store.put_blob_stream,
            ) as stream_put:
                result = Ingestor(
                    store,
                    adapters=[adapter],
                ).ingest(
                    GitHubFileSource(
                        "o",
                        "r",
                        "main",
                        "README.md",
                    )
                )

            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            stream_put.assert_called_once()
            self.assertEqual(
                result.source.source_identity["commit"],
                "a" * 40,
            )
            self.assertEqual(
                result.source.claimed_metadata["requested_ref"],
                "main",
            )
            self.assertEqual(
                (store.root / result.raw_artifact.storage_locator).read_bytes(),
                b"hello from streamed github\n",
            )

    def test_github_ref_is_resolved_to_exact_commit_in_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeGitHubTransport()
            ingestor = Ingestor(
                FileSystemStore(Path(tmp) / ".ingest"),
                adapters=[GitHubAdapter(transport)],
            )
            result = ingestor.ingest(GitHubFileSource("o", "r", "main", "README.md"))
            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            self.assertIn("@" + "a" * 40 + "/README.md", result.source.locator)
            self.assertEqual(result.source.claimed_metadata["requested_ref"], "main")
            self.assertEqual(result.source.source_identity["commit"], "a" * 40)

    def test_message_event_time_is_claimed_metadata_not_observation_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingestor = Ingestor(
                FileSystemStore(Path(tmp) / ".ingest"),
                adapters=[MessageAdapter()],
            )
            result = ingestor.ingest(
                MessageSource("m1", {"text": "hello"}, source="bus", event_time="2026-09-20T12:00:00Z")
            )
            self.assertEqual(result.source.claimed_metadata["event_time"], "2026-09-20T12:00:00Z")
            self.assertNotEqual(result.source.observed_at, "2026-09-20T12:00:00Z")
            self.assertEqual(
                result.source.observed_metadata["ingestion_time_semantics"],
                "OBSERVATION_TIME_NOT_EVENT_TIME",
            )


if __name__ == "__main__":
    unittest.main()
