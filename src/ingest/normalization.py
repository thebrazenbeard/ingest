from __future__ import annotations

import codecs
from collections.abc import Iterable, Iterator
import json
import unicodedata

from .canonical import canonical_json


NORMALIZER_VERSION = "ingest-normalizer-v1"


class NormalizationError(ValueError):
    pass


def _clean_media_type(media_type: str | None) -> str | None:
    if media_type is None:
        return None
    return media_type.split(";", 1)[0].strip().lower() or None


class StreamingMediaSniffer:
    _ASCII_WHITESPACE = frozenset(b" \t\n\r\v\f")

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self._utf8_valid = True
        self._contains_nul = False
        self._first_non_whitespace: int | None = None

    def feed(self, chunk: bytes) -> None:
        if self._first_non_whitespace is None:
            for value in chunk:
                if value not in self._ASCII_WHITESPACE:
                    self._first_non_whitespace = value
                    break
        if b"\x00" in chunk:
            self._contains_nul = True
        if self._utf8_valid:
            try:
                self._decoder.decode(chunk, final=False)
            except UnicodeDecodeError:
                self._utf8_valid = False

    def finalize(self) -> str | None:
        if self._utf8_valid:
            try:
                self._decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                self._utf8_valid = False
        if not self._utf8_valid or self._contains_nul:
            return "application/octet-stream"
        if self._first_non_whitespace in (ord("{"), ord("[")):
            return None
        return "text/plain"


_JSONL_LINE_BREAKS = frozenset(
    ("\n", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")
)


def _take_complete_jsonl_lines(
    buffer: str,
    *,
    final: bool,
) -> tuple[list[str], str]:
    lines: list[str] = []
    start = 0
    index = 0
    while index < len(buffer):
        value = buffer[index]
        if value == "\r":
            if index + 1 == len(buffer) and not final:
                break
            end = (
                index + 2
                if index + 1 < len(buffer) and buffer[index + 1] == "\n"
                else index + 1
            )
            lines.append(buffer[start:index])
            start = end
            index = end
            continue
        if value in _JSONL_LINE_BREAKS:
            lines.append(buffer[start:index])
            start = index + 1
        index += 1

    remainder = buffer[start:]
    if final and remainder:
        lines.append(remainder)
        remainder = ""
    return lines, remainder


def _canonicalize_jsonl_line(line: str, line_number: int) -> bytes | None:
    if not line.strip():
        return None
    try:
        value = json.loads(line)
        return (canonical_json(value) + "\n").encode("utf-8")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise NormalizationError(
            f"invalid JSONL line {line_number}: {exc}"
        ) from exc


def normalize_jsonl_stream(chunks: Iterable[bytes]) -> Iterator[bytes]:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    buffer = ""
    line_number = 0
    first_json_error: NormalizationError | None = None
    utf8_error = False

    def process(lines: list[str]) -> Iterator[bytes]:
        nonlocal line_number, first_json_error
        for line in lines:
            line_number += 1
            if first_json_error is not None:
                continue
            try:
                normalized = _canonicalize_jsonl_line(line, line_number)
            except NormalizationError as exc:
                first_json_error = exc
                continue
            if normalized is not None:
                yield normalized

    for chunk in chunks:
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("JSONL stream chunks must be bytes-like")
        if utf8_error:
            continue
        try:
            buffer += decoder.decode(bytes(chunk), final=False)
        except UnicodeDecodeError:
            utf8_error = True
            continue
        lines, buffer = _take_complete_jsonl_lines(
            buffer,
            final=False,
        )
        yield from process(lines)

    if not utf8_error:
        try:
            buffer += decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            utf8_error = True

    if utf8_error:
        raise NormalizationError("JSONL is not valid UTF-8")

    lines, buffer = _take_complete_jsonl_lines(buffer, final=True)
    yield from process(lines)
    if buffer:
        raise AssertionError("streaming JSONL line buffer was not drained")
    if first_json_error is not None:
        raise first_json_error


def sniff_media_type(data: bytes) -> str:
    stripped = data.lstrip()
    if stripped.startswith((b"{", b"[")):
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        else:
            return "application/json"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    if "\x00" in text:
        return "application/octet-stream"
    return "text/plain"


def normalize_bytes(data: bytes, media_type: str) -> bytes | None:
    media_type = _clean_media_type(media_type) or "application/octet-stream"
    if media_type in {"application/json", "text/json"}:
        try:
            value = json.loads(data.decode("utf-8"))
            return canonical_json(value).encode("utf-8")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NormalizationError(f"invalid JSON: {exc}") from exc
    if media_type in {"application/x-ndjson", "application/jsonl"}:
        return b"".join(normalize_jsonl_stream((data,)))
    if media_type.startswith("text/"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NormalizationError("text payload is not valid UTF-8") from exc
        text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
        return text.encode("utf-8")
    return None
