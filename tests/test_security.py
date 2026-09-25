import unittest

from ingest.adapters.base import PolicyRejected
from ingest.adapters.http import HttpAdapter
from ingest.policy import IngestPolicy


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


if __name__ == "__main__":
    unittest.main()
