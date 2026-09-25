# Ingest V1 Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-neutral intake engine that preserves raw source bytes, emits deterministic content/provenance identities, normalizes supported formats, and records auditable receipts.

**Architecture:** Python stdlib-only core with explicit source adapters, deterministic canonical hashing, an immutable filesystem content-addressed store, and a single `Ingestor` pipeline. Provider/network/database-specific behavior stays behind adapter/store boundaries.

**Tech Stack:** Python 3.12+, `dataclasses`, `urllib`, `pathlib`, `hashlib`, `json`, `unittest`, GitHub Actions.

## Global Constraints

- Raw bytes are immutable and never replaced by normalized bytes.
- Source identity and content identity stay distinct.
- Ingestion/observation time never substitutes for event time.
- Exact GitHub commit identity is required for GitHub provenance.
- Similarity never establishes identity or semantic equivalence.
- Receipt output cannot promote content into truth/currentness/authority.
- No acquired content execution.
- V1 core has no required third-party runtime dependency.

---

### Task 1: Deterministic models, normalization, and content store

**Files:** `src/ingest/canonical.py`, `model.py`, `policy.py`, `normalization.py`, `storage.py`; tests `test_canonical.py`, `test_normalization.py`, `test_pipeline.py`.

**Interfaces:** canonical JSON/digest helpers; immutable source/artifact/receipt/result models; `IngestPolicy`; `FileSystemStore`.

- [x] Add failing canonicalization/normalization/pipeline tests.
- [x] Observe import/missing-behavior failures.
- [x] Implement canonical SHA-256 identities, narrow normalization, and atomic immutable storage.
- [x] Verify exact duplicate vs shared-artifact semantics.

### Task 2: Source adapters and policy boundaries

**Files:** `src/ingest/adapters/*`; tests `test_adapters_and_policy.py`.

**Interfaces:** `SourceAdapter.acquire`, `TextSource`, `BytesSource`, `FileSource`, `UrlSource`, `GitHubFileSource`, `MessageSource`.

- [x] Implement bounded text/bytes and file acquisition.
- [x] Implement HTTP(S) policy checks and bounded manual redirects.
- [x] Implement GitHub ref→exact-commit acquisition with injected credentials/transport.
- [x] Preserve message event time as claimed metadata separate from observation time.
- [x] Add adversarial parser-identity and JSONL tests; observe and fix both failures.

### Task 3: Pipeline receipts, quarantine, derivations, and CLI

**Files:** `src/ingest/pipeline.py`, `cli.py`; schemas under `schemas/`; CLI tests.

**Interfaces:** `Ingestor.ingest`, `Ingestor.ingest_many`, CLI commands, `INGEST_RECORD_V1`, `INGEST_STAGE_RECEIPT_V1`.

- [x] Emit receipt-digest-bound stage records.
- [x] Preserve raw before structured quarantine.
- [x] Emit explicit `NORMALIZED_FROM` derivation edges.
- [x] Add CLI commands and verify machine/human output plus exit status.
- [x] Validate example record/receipt shapes against repository schemas.

### Task 4: Repository/operator surface and full verification

**Files:** `README.md`, design/security/source-review docs, licensing/governance files, `.github/workflows/ci.yml`.

**Interfaces:** repository contract and CI test command.

- [x] Record the complete portfolio screening and exact admitted donor heads.
- [x] Document security caveats and provider-neutral extension rules.
- [x] Build/install into an isolated target with no runtime dependencies and run the complete `unittest` suite. (A pristine venv could not fetch its build backend because this execution environment blocks outbound DNS; the same local setuptools backend built the wheel successfully with `--no-build-isolation`.)
- [ ] Initialize/populate GitHub `main`, read back critical files, and verify the exact resulting head.

## Externally visible decisions

Resolved for V1:

- stdout carries result data; no routine result is written to stderr;
- default CLI output is compact JSON;
- `--human` is explicit human output;
- `ACCEPTED` and `DUPLICATE` exit `0`; all other ingest states exit `2`;
- immutable record collisions fail rather than overwrite;
- exact duplicate observations create new receipt evidence without rewriting the original record;
- semantic deduplication is out of scope.
