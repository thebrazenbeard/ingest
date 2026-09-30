# Ingest Roadmap

Updated: 2026-09-29

This roadmap records engineering frontiers, not promises of installed/runtime behavior.

## Landed on current main

- provider-neutral V1 intake core;
- deterministic raw/normalized artifact identity;
- source/provenance identity separation;
- strict JSON/JSONL/text normalization;
- local-root and link controls;
- HTTP private-network controls and validated-address connection binding;
- GitHub exact-commit/blob verification;
- immutable filesystem CAS;
- durable record/receipt/derivation model;
- fail-closed record read verification;
- same-identity concurrency arbitration;
- managed-path redirection protection;
- stale temp cleanup.

## Open hardening stack

### PR #8 — donor research

Cross-domain review for capture systems, scientific runs, provider registries, memory acquisition, orchestration runtimes, streaming I/O, and provenance boundaries.

### PR #9 — record graph audit

Operator-facing read-only audit over persisted record graphs and unexpected `records/` entries.

### PR #10 — bounded artifact verification

Incremental SHA-256 verification and collision checks without full-blob materialization; ctime-only hard-link metadata drift is excluded from content mutation.

### PR #11 — streaming blob publication

Bounded chunked write, incremental SHA-256, fsynced staging, create-only CAS publication, dedupe verification, and failed-temp cleanup.

### PR #12 — streaming local-file raw capture

Local files use descriptor-bound streaming raw capture into CAS. Existing normalizers remain byte-oriented after raw admission.

### PR #13 — streaming media pre-sniff

Reuses raw source chunks for exact binary/text pre-classification and skips raw-blob readback when parser-driving semantics are opaque; JSON-looking streams retain full byte classification.

### PR #14 — streaming HTTP capture

Moves HTTP response bodies onto the streaming CAS path while retaining redirect, timeout, validated-address, final-destination, provenance, and cleanup controls.

### PR #15 — streaming GitHub capture

Moves the default GitHub transport onto metadata-preflight + raw-blob streaming while preserving exact-commit provenance and incremental Git object verification; custom non-streaming transports retain buffered fallback.

## Next implementation frontiers

### 1. Streaming media pre-sniff — implemented on hardening line

Local-file chunks now feed an incremental UTF-8/NUL/leading-token sniffer during raw CAS publication. Definitive opaque/non-normalized inputs can avoid post-capture blob materialization. JSON-looking content still falls back to the original full byte sniffer so semantics remain stable.

### 2. Incremental normalization ? JSONL implemented on hardening line

JSONL/NDJSON now uses incremental UTF-8 decoding, Python-compatible line-boundary semantics, line-by-line canonicalization, verified raw CAS chunk iteration, and streamed derived CAS publication. Existing canonical bytes and error semantics are preserved, so `ingest-normalizer-v1` remains correct.

Remaining work:

- UTF-8 text with incremental decoder plus NFC boundary handling;
- monolithic/large JSON only if a deterministic bounded parser strategy is acceptable;
- remove generic sniff-stage materialization for JSON-looking streams without changing raw media classification semantics.

Any semantic normalizer change must be identity-visible.

### 3. HTTP streaming acquisition — implemented on hardening line

HTTP response bodies now stream through the CAS after requested/final URL validation and provenance binding while preserving address pinning, redirects, timeouts, hard byte ceilings, and response/temp cleanup.

### 4. GitHub streaming/large object path — implemented on hardening line

The default GitHub transport resolves mutable refs to exact commits, preflights blob size/identity metadata, streams raw blob bytes into CAS, recomputes Git object identity incrementally, and retains buffered fallback for custom transports without streaming support.

### 5. Segmented and range-based sources

Add explicit segment/range manifests only after concrete adapters need them. Preserve exact raw representation and keep segment metadata provenance-bound.

### 6. Advisory source discovery

Potential optional adapter contract:

`discover(source, policy) -> SourceDescriptor | None`

Discovery may report estimated size, replayability, volatility, partitions/ranges, session identity, and media hints. It is advisory and must never replace acquisition-time validation.

### 7. Acquisition session recovery

Only if long-running streams justify it, add a minimal capture-session state machine for recovery/finalization.

Do not turn Ingest into a workflow engine.

`CAPTURE_SESSION_ID != ARTIFACT_ID != INGEST_ID`

### 8. Whole-store inventory audit ? implemented on hardening line

`audit-store` inventories records, blobs, receipts, derivations, and temp files; validates published objects and managed structure; reports objects unreferenced by valid record graphs; distinguishes `ISSUES` from `CORRUPT`; and performs no automatic deletion. A future scale pass should bound/report very large inventories without changing those semantics.

## Non-goals that remain non-goals

- truth adjudication;
- semantic similarity as identity;
- arbitrary installed-plugin auto-execution;
- DAG/workflow scheduling;
- worker queues;
- SCADA control;
- model routing;
- hardware control;
- automatic destructive garbage collection;
- runtime activation merely because repository source exists.
