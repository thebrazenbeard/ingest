import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ingest.cli import main


class CliTests(unittest.TestCase):
    def test_text_default_is_machine_json_and_duplicate_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                first = main(["--store", str(Path(tmp) / ".ingest"), "text", "hello", "--locator", "urn:cli"])
            payload = json.loads(output.getvalue())
            self.assertEqual(first, 0)
            self.assertEqual(payload["status"], "ACCEPTED")

            output = io.StringIO()
            with redirect_stdout(output):
                second = main(["--store", str(Path(tmp) / ".ingest"), "text", "hello", "--locator", "urn:cli"])
            self.assertEqual(second, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "DUPLICATE")

    def test_human_mode_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--store", str(Path(tmp) / ".ingest"), "--human", "text", "hello"])
            self.assertEqual(code, 0)
            self.assertTrue(output.getvalue().startswith("ACCEPTED "))
            self.assertNotIn('"schema"', output.getvalue())

    def test_inspect_missing_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--store", str(Path(tmp) / ".ingest"), "inspect", "f" * 64])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
