import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from ingest import FileSystemStore, IngestPolicy, IngestStatus, Ingestor, UrlSource
from ingest.adapters.base import AcquisitionFailed, PolicyRejected
from ingest.adapters.http import HttpAdapter


class SecurityTests(unittest.TestCase):
    def test_http_disabled_by_default(self):
        with self.assertRaises(PolicyRejected):
            HttpAdapter._check_url("http://example.com/data", IngestPolicy())

    def test_loopback_denied_even_when_plain_http_explicitly_enabled(self):
        with self.assertRaises(PolicyRejected):
            HttpAdapter._check_url(
                "http://127.0.0.1/data",
                IngestPolicy(allow_http=True),
            )

    def test_default_http_transport_connects_to_validated_ip_not_hostname(self):
        public_ip = "93.184.216.34"
        resolved = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (public_ip, 0))]
        attempted = []

        def fail_connect(address, *_args, **_kwargs):
            attempted.append(address)
            raise OSError("stop after address selection")

        with patch("ingest.adapters.http.socket.getaddrinfo", return_value=resolved), patch(
            "socket.create_connection", side_effect=fail_connect
        ):
            with self.assertRaises(AcquisitionFailed):
                HttpAdapter().acquire(
                    UrlSource("http://rebind.test/resource"),
                    IngestPolicy(allow_http=True),
                )

        self.assertTrue(attempted)
        self.assertEqual(attempted[0][0], public_ip)

    def test_default_http_transport_preserves_redirect_behavior(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", "/final")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"hello")

            def log_message(self, _format, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            acquisition = HttpAdapter().acquire(
                UrlSource(f"http://127.0.0.1:{port}/start"),
                IngestPolicy(allow_http=True, deny_private_networks=False),
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(acquisition.data, b"hello")
        self.assertEqual(acquisition.source.observed_metadata["redirects"], 1)

    def test_ingestor_streams_http_capture_instead_of_buffered_acquire(self):
        class ChunkedResponse:
            status = 200
            headers = {"Content-Type": "application/octet-stream"}

            def __init__(self, url):
                self._url = url
                self._chunks = iter([b"alpha", b"beta", b""])
                self.closed = False

            def geturl(self):
                return self._url

            def read(self, _limit):
                return next(self._chunks)

            def close(self):
                self.closed = True

        class StreamingOpener:
            def __init__(self, response):
                self.response = response

            def open(self, request, timeout):
                return self.response

        with tempfile.TemporaryDirectory() as tmp:
            response = ChunkedResponse("https://example.com/data.bin")
            adapter = HttpAdapter(opener=StreamingOpener(response))
            store = FileSystemStore(Path(tmp) / ".ingest")

            with patch.object(
                adapter,
                "acquire",
                side_effect=AssertionError(
                    "buffered HttpAdapter.acquire should not be used"
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
                    UrlSource("https://example.com/data.bin"),
                    IngestPolicy(deny_private_networks=False),
                )

            self.assertEqual(result.status, IngestStatus.ACCEPTED)
            stream_put.assert_called_once()
            self.assertTrue(response.closed)
            self.assertEqual(
                (store.root / result.raw_artifact.storage_locator).read_bytes(),
                b"alphabeta",
            )

    def test_http_stream_checks_final_destination_before_body_read(self):
        class PrivateFinalResponse:
            status = 200
            headers = {"Content-Type": "text/plain"}

            def __init__(self):
                self.read_called = False
                self.closed = False

            def geturl(self):
                return "http://127.0.0.1/private"

            def read(self, _limit):
                self.read_called = True
                return b"must-not-be-read"

            def close(self):
                self.closed = True

        class StreamingOpener:
            def __init__(self):
                self.response = PrivateFinalResponse()

            def open(self, request, timeout):
                return self.response

        opener = StreamingOpener()
        adapter = HttpAdapter(opener=opener)
        with patch(
            "ingest.adapters.http._resolve_addresses",
            side_effect=lambda host: (
                ("127.0.0.1",)
                if host == "127.0.0.1"
                else ("93.184.216.34",)
            ),
        ):
            with self.assertRaises(PolicyRejected):
                adapter.acquire_stream(
                    UrlSource("https://example.com/start"),
                    IngestPolicy(),
                )

        self.assertFalse(opener.response.read_called)
        self.assertTrue(opener.response.closed)

    def test_http_stream_over_limit_closes_and_publishes_no_raw_blob(self):
        class OversizeResponse:
            status = 200
            headers = {"Content-Type": "application/octet-stream"}

            def __init__(self, url):
                self._url = url
                self._chunks = iter([b"abc", b"def", b""])
                self.closed = False

            def geturl(self):
                return self._url

            def read(self, _limit):
                return next(self._chunks)

            def close(self):
                self.closed = True

        class StreamingOpener:
            def __init__(self, response):
                self.response = response

            def open(self, request, timeout):
                return self.response

        with tempfile.TemporaryDirectory() as tmp:
            response = OversizeResponse("https://example.com/large.bin")
            adapter = HttpAdapter(opener=StreamingOpener(response))
            store = FileSystemStore(Path(tmp) / ".ingest")
            result = Ingestor(
                store,
                adapters=[adapter],
            ).ingest(
                UrlSource("https://example.com/large.bin"),
                IngestPolicy(max_bytes=5, deny_private_networks=False),
            )

            self.assertEqual(result.status, IngestStatus.REJECTED)
            self.assertTrue(response.closed)
            blob_root = store.root / "blobs"
            blob_files = (
                []
                if not blob_root.exists()
                else [
                    path
                    for path in blob_root.rglob("*")
                    if path.is_file()
                ]
            )
            self.assertEqual(blob_files, [])

    def test_custom_opener_without_private_denial_keeps_its_own_resolution(self):
        class FailingOpener:
            def open(self, request, timeout):
                raise URLError("custom transport stop")

        with patch(
            "ingest.adapters.http._resolve_addresses",
            side_effect=AssertionError("custom opener should own resolution"),
        ):
            with self.assertRaises(AcquisitionFailed):
                HttpAdapter(opener=FailingOpener()).acquire(
                    UrlSource("http://custom.invalid/resource"),
                    IngestPolicy(allow_http=True, deny_private_networks=False),
                )


if __name__ == "__main__":
    unittest.main()
