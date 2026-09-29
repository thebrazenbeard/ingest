# Streaming Normalization V1

Status: JSONL / NDJSON IMPLEMENTED ON HARDENING LINE
Date: 2026-09-29

## Purpose

Streaming raw acquisition removes the requirement for adapters to construct a complete source `bytes` object before persistence. Streaming normalization addresses the next memory peak: producing a canonical derivative without simultaneously holding the complete raw artifact and complete normalized artifact in memory.

V1 starts with JSONL/NDJSON because its semantic record boundaries are explicit line boundaries.

## JSONL contract

For effective media type `application/x-ndjson` or `application/jsonl`, the hardening line performs:

`verified raw CAS chunks -> incremental UTF-8 decode -> logical lines -> canonical JSON per nonblank line -> streamed normalized CAS publication`

Each nonblank line is parsed with `json.loads()` and serialized with the existing `canonical_json()` function. Canonical lines are terminated with one LF byte. Blank logical lines produce no normalized output.

The resulting bytes are intentionally identical to the existing buffered V1 normalizer.

## Line semantics

The streaming splitter preserves Python `str.splitlines()` boundaries used by the prior implementation, including LF, CR, CRLF, vertical tab, form feed, file/group/record separators, NEL, and Unicode line/paragraph separators. A terminal CR is deferred until the next chunk so a following LF is not double-counted.

## Error semantics

Buffered V1 decoded the entire JSONL payload as UTF-8 before parsing individual lines. The streaming implementation preserves that observable precedence:

- invalid UTF-8 anywhere yields `JSONL is not valid UTF-8`;
- otherwise the first invalid nonblank JSON line yields the same `invalid JSONL line N: ...` error as buffered V1.

The transform continues consuming the verified raw iterator after remembering a JSON-line error so later UTF-8 corruption retains precedence and raw CAS verification reaches end-of-stream.

A normalization failure aborts derived staging; no normalized CAS artifact is published. The raw artifact remains available as quarantine evidence.

## Store boundaries

`FileSystemStore.iter_blob_chunks()` validates artifact identity/path/size, reads through no-follow managed storage, hashes every yielded chunk, and verifies size/stability/SHA-256 when fully exhausted.

External source admission remains mandatory-bounded:

`put_blob_stream(..., max_bytes=<positive bound>)`

Derived normalization uses a separate:

`put_derived_blob_stream(...)`

The derived path deliberately does not invent a new size policy. Buffered V1 normalization had no independent derived-size ceiling, and canonical JSON can expand relative to terse notation (`1e3` becomes `1000.0`). Keeping the APIs separate prevents the derived rule from being reused accidentally for untrusted source admission.

## Identity

`NORMALIZER_VERSION` remains `ingest-normalizer-v1` because canonical bytes and normalization error semantics are unchanged. An implementation change alone is not an identity change.

Any future change to canonical bytes or parser semantics must change the normalizer version and therefore the ingest identity.

## Current claim ceiling

JSONL normalization and normalized-artifact publication are streaming, but JSONL intake is not always end-to-end constant-memory.

The generic media sniffer intentionally leaves JSON-looking payloads beginning with `{` or `[` unresolved until the persisted raw artifact can be classified as a complete JSON document or plain text. Therefore the raw artifact may still be materialized once for exact media classification before the streaming JSONL transform runs.

`STREAMING_JSONL_NORMALIZATION != FULLY_STREAMING_JSONL_INGEST`

The remaining boundary is generic media classification, not JSONL canonicalization or derived persistence.

## Non-goals

This implementation does not yet provide incremental NFC normalization for arbitrary text, streaming canonicalization of one monolithic JSON document, a new derived-output size policy, resumable normalization sessions, or workflow scheduling/retries.
