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

## Next implementation frontiers

### 1. Remove unnecessary post-capture blob materialization

Preserve current media-type semantics while avoiding full raw readback for sources that are provably opaque or can be sniffed incrementally.

Do not silently change classification/dedup semantics merely to save memory.

### 2. Incremental normalization

Design streaming-safe normalizers for:

- UTF-8 text with incremental decoder + NFC boundary handling;
- JSONL line-by-line canonicalization;
- large JSON only if a deterministic bounded parser strategy is acceptable.

Any new normalizer version must be identity-visible.

### 3. HTTP streaming acquisition

Move the default HTTP transport from buffered response bytes to bounded chunk delivery while preserving:

- address validation/pinning;
- redirect checks;
- timeout behavior;
- exact URL provenance digesting;
- hard byte ceilings;
- failure cleanup.

### 4. GitHub streaming/large object path

Keep exact commit/blob binding. Avoid weakening Git object digest verification while introducing chunked transport.

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

### 8. Whole-store inventory audit

Current record audit follows record graphs. A separate inventory audit may later detect orphan blobs, receipts, derivations, stale staging, and unexpected directory entries without deleting them automatically.

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
