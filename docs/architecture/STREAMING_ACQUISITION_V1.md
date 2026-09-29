# Streaming Acquisition V1

Status: IMPLEMENTED FOR LOCAL-FILE RAW CAPTURE ON HARDENING LINE  
Date: 2026-09-29

## Purpose

This contract lets Ingest admit large sources without requiring the acquisition boundary to first construct one complete in-memory `bytes` object.

The invariant does not change:

`artifact_id = sha256:<SHA256(exact persisted bytes)>`

Streaming changes how bytes reach the content-addressed store, not what artifact identity means.

## Implemented boundary

`StreamingAcquisition` carries:

- a bounded iterable of bytes-like chunks;
- the same `SourceRef` provenance object used by buffered acquisition;
- an optional claimed media type.

`FileSystemStore.put_blob_stream()`:

1. creates managed temporary staging under the CAS;
2. consumes chunks incrementally;
3. rejects a stream as soon as the next chunk would exceed `max_bytes`;
4. computes SHA-256 and byte count incrementally;
5. flushes and `fsync`s staged bytes;
6. derives the final SHA-256 CAS path;
7. create-only publishes by hard link;
8. verifies an already-existing/concurrent object through bounded descriptor hashing;
9. sync-attempts the final directory for a new publication;
10. removes temporary staging on success, duplicate, or failure.

Local `FileAdapter.acquire_stream()` additionally preserves the existing file controls:

- configured root confinement;
- link/junction rejection unless explicitly allowed;
- pre-open versus opened file identity checks;
- hard policy byte ceiling;
- same-descriptor post-read stability checks;
- size consistency;
- descriptor closure on every path.

## Current pipeline behavior

For local files, raw capture is now:

`file descriptor -> bounded chunks -> fsynced staging -> SHA-256 CAS publication`

The pipeline then opens the persisted raw artifact through the store when the existing V1 content sniffer/normalizer needs a byte payload.

Therefore:

`STREAMING_RAW_CAPTURE != FULLY_STREAMING_PIPELINE`

Current byte materialization can still occur after raw publication for:

- media sniffing;
- UTF-8 normalization;
- JSON canonicalization;
- JSONL canonicalization.

Streamed local-file capture now performs an incremental UTF-8/NUL/leading-token pre-sniff while bytes are already flowing into CAS. Definitive opaque/text classification therefore avoids a second raw-blob read when downstream normalization is not needed. JSON-looking streams remain conservative: if the first non-whitespace byte is `{` or `[`, the persisted raw artifact is materialized and passed through the original full JSON-aware sniffer so classification semantics do not change.

## Failure semantics

A streaming source that fails or changes before finalization does not publish the temporary raw blob as a completed CAS artifact.

A stream that exceeds `max_bytes` fails before the over-limit chunk is written to staging.

A concurrent equal publication resolves to the already-existing content-addressed object.

A concurrent different object cannot occupy the same SHA-256 path without producing a store conflict.

## Identity and session boundary

V1 deliberately does not add a workflow/run/session identity merely because acquisition is streaming.

A future capture/session identifier may be useful for resumable long-running acquisition, but it must remain distinct from final evidence identity:

`CAPTURE_SESSION_ID != ARTIFACT_ID != INGEST_ID`

Artifact and ingest identity continue to derive from finalized evidence, not scheduler state.

## Explicit non-goals

This implementation does not yet provide:

- streaming HTTP response admission;
- streaming GitHub file admission;
- incremental text/JSON/JSONL normalization beyond the new streaming pre-sniff;
- resumable partial uploads;
- segmented/range manifests;
- orphan-object auditing;
- workflow scheduling, retries, approvals, or DAG execution;
- cryptographic authenticity against a writer able to coherently rewrite the entire store.

Those belong to later bounded changes.

## HTTP streaming

`HttpAdapter.acquire_stream()` now uses the same streaming CAS path. The adapter deliberately separates response establishment from response-body consumption:

1. validate requested URL/scheme/network policy;
2. resolve and pin the default transport connection to validated addresses;
3. apply bounded redirect policy;
4. validate the returned final URL before reading its body;
5. bind secret-safe requested/final URL provenance;
6. yield bounded response chunks;
7. close the response on success or failure.

The buffered `HttpAdapter.acquire()` remains for direct adapter callers and reuses the same response-establishment/provenance boundary. Ingestor prefers `acquire_stream()` when available.
