import unittest

from ingest import normalization as normalization_module
from ingest.normalization import NormalizationError, normalize_bytes, sniff_media_type


class NormalizationTests(unittest.TestCase):
    def test_text_normalization_is_nfc_and_lf_without_stripping(self):
        raw = "Cafe\u0301\r\nline 2  \r".encode("utf-8")
        normalized = normalize_bytes(raw, "text/plain")
        self.assertEqual(normalized, "Café\nline 2  \n".encode("utf-8"))

    def test_json_is_canonicalized(self):
        raw = b'{"z": 2, "a": [3, 1]}'
        self.assertEqual(normalize_bytes(raw, "application/json"), b'{"a":[3,1],"z":2}')
        self.assertEqual(sniff_media_type(raw), "application/json")

    def test_streaming_jsonl_matches_buffered_across_chunk_boundaries(self):
        data = (
            '{"b":2,"a":"caf?"}\r\n'
            '\r\n'
            '{"z":0}\u2028'
            '{"nested":{"b":2,"a":1}}'
        ).encode("utf-8")
        split_points = [1, 7, 15, 18, 22, 31, 39, len(data)]
        chunks = []
        start = 0
        for end in split_points:
            chunks.append(data[start:end])
            start = end

        streamed = b"".join(normalization_module.normalize_jsonl_stream(iter(chunks)))
        buffered = normalize_bytes(data, "application/x-ndjson")

        self.assertEqual(streamed, buffered)

    def test_streaming_jsonl_preserves_buffered_invalid_line_number(self):
        data = b'{"a":1}\r\n\r\n{"broken":}\r\n'
        chunks = [data[:9], data[9:11], data[11:18], data[18:]]

        with self.assertRaises(NormalizationError) as streamed_error:
            b"".join(normalization_module.normalize_jsonl_stream(iter(chunks)))
        with self.assertRaises(NormalizationError) as buffered_error:
            normalize_bytes(data, "application/x-ndjson")

        self.assertEqual(str(streamed_error.exception), str(buffered_error.exception))

    def test_streaming_jsonl_preserves_utf8_error_precedence(self):
        data = b'{"broken":}\n' + b'\xff'
        chunks = [data[:6], data[6:12], data[12:]]

        with self.assertRaises(NormalizationError) as streamed_error:
            b"".join(
                normalization_module.normalize_jsonl_stream(iter(chunks))
            )
        with self.assertRaises(NormalizationError) as buffered_error:
            normalize_bytes(data, "application/x-ndjson")

        self.assertEqual(
            str(streamed_error.exception),
            "JSONL is not valid UTF-8",
        )
        self.assertEqual(
            str(streamed_error.exception),
            str(buffered_error.exception),
        )

    def test_invalid_json_fails_as_json(self):
        with self.assertRaises(NormalizationError):
            normalize_bytes(b'{"bad":', "application/json")


if __name__ == "__main__":
    unittest.main()
