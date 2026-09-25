# Ingest V1 — Universal Intake Boundary Design

Status: APPROVED
Date: 2026-09-25
Repository: `thebrazenbeard/ingest`

## Purpose

Ingest is the universal provider-neutral intake layer for heterogeneous information. It accepts source material, preserves exact raw bytes, creates deterministic normalized derivatives when explicitly supported, binds source and transformation provenance, and emits machine-readable records and receipts for downstream systems.

Ingest is deliberately below downstream ontology. Intake is not truth adjudication, semantic interpretation, currentness, authority, memory admission, or runtime activation.

## Required distinctions

`SOURCE_LOCATOR != SOURCE_AUTHORSHIP`

`RETRIEVAL != ADMISSION`

`INGESTION_TIME != EVENT_TIME`

`RAW_BYTES != NORMALIZED_DERIVATIVE`

`CONTENT_IDENTITY != SOURCE_IDENTITY`

`SIMILARITY != IDENTITY`

`RECEIPT != TRUTH`

`SOURCE != INTERPRETATION`

`MUTABLE_REF != IMMUTABLE_PROVENANCE`

`SOURCE_IMPLEMENTATION != INSTALLED_RUNTIME`

## V1 source classes

1. inline text and bytes;
2. local files;
3. HTTP(S) resources;
4. GitHub repository files with exact-commit resolution;
5. generic message/event envelopes.

Structured JSON and JSONL are transformations over acquired bytes rather than separate truth-bearing source classes.

## Canonical record model

### SourceRef

A `SourceRef` contains:

- `scheme`;
- `locator`;
- adapter name and version;
- `observed_at`;
- stable `source_identity` used for deterministic ingest identity;
- `claimed_metadata` supplied by the source or caller;
- `observed_metadata` established by the adapter.

`observed_at` never substitutes for an event timestamp supplied by source evidence.

### Artifact

An artifact is an immutable content-addressed byte sequence with:

- SHA-256 identity;
- byte length;
- media type;
- artifact role (`raw` or `normalized`);
- storage locator.

Two source observations may share an artifact without being the same ingest event.

### Ingest record

An ingest record binds:

- deterministic `ingest_id`;
- source identity and provenance;
- raw artifact;
- optional normalized artifact;
- status;
- evidence class;
- normalizer version;
- policy identity;
- stage receipts;
- derivation edges;
- warnings and bounded error state.

### Receipt

Every completed pipeline stage can emit an append-only `INGEST_STAGE_RECEIPT_V1` with a canonical SHA-256 receipt digest. Receipts report observations and transformations. They cannot promote content into truth or authority.

### Derivation

A derivation is a typed immutable edge between artifacts. V1 uses `NORMALIZED_FROM`. Future chunking/extraction must add new explicit relation types rather than mutating source artifacts.

## Pipeline

1. **Acquire** through a source adapter.
2. **Bound** size and source-policy constraints.
3. **Sniff** content type and compare it with claimed type.
4. **Persist raw** bytes to content-addressed storage.
5. **Identify ingest** from stable source identity, raw hash, parser-driving media type, normalizer version, and policy digest.
6. **Deduplicate** by exact ingest identity.
7. **Normalize** only supported formats.
8. **Persist normalized** derivative and relation.
9. **Record** the accepted or quarantined intake state.
10. **Emit result** without silently strengthening evidence.

## Deterministic identity

Artifact identity:

`SHA256(exact persisted bytes)`

Ingest identity:

`SHA256(canonical JSON(source identity + raw SHA256 + parser-driving media type + normalizer version + policy identity))`

Observation timestamps are excluded from deterministic identity.

The design intentionally mirrors Project Runner's useful rule that provenance paths may explain how something was discovered without defining the underlying work/content identity. In Ingest, raw bytes deduplicate globally while source observations retain their own provenance identity.

## Normalization V1

### UTF-8 text

- strict UTF-8 decode;
- CRLF/CR → LF;
- Unicode NFC;
- no whitespace trimming or rewriting.

### JSON

- strict parse;
- canonical UTF-8 JSON;
- sorted object keys;
- compact separators;
- Unicode preserved.

### JSONL / NDJSON

- blank lines ignored;
- each non-empty line must parse independently;
- each object is canonicalized independently;
- normalized output ends with LF when non-empty.

### Opaque binary

No derivative is created in V1 unless a registered future parser explicitly owns that transformation.

## Failure model

`REJECTED` means policy denied admission before durable raw storage.

`QUARANTINED` means raw bytes were safely stored but structured interpretation is unsafe or invalid, such as a file claiming JSON that does not parse as JSON.

`FAILED` means acquisition or internal execution could not establish a reliable admitted result.

`PARTIAL` is reserved for future optional derivations where the raw/core record remains safe but nonessential processing is incomplete.

## GitHub provenance

A requested branch or tag is a mutable acquisition hint. The GitHub adapter resolves it to an exact commit before reading file content, and `SourceRef.source_identity` binds owner, repository, exact commit, and path. The originally requested ref remains claimed metadata.

Credential material belongs to the transport object, not the source record, receipt, locator, or artifact.

## Security boundary

V1 requires:

- no acquired-code execution;
- hard input byte ceilings;
- local allowed-root confinement when configured;
- symlink denial by default;
- HTTPS by default;
- HTTP only by explicit policy;
- bounded redirects;
- required network timeouts;
- private/loopback/link-local network denial by default;
- raw preservation before structured parsing when admission is safe;
- no automatic archive/container extraction.

Pre-resolution private-network checks reduce SSRF exposure but do not claim complete DNS-rebinding resistance. A hardened remote-fetch service can later replace the default transport behind the same adapter contract.

## Storage boundary

V1 ships a filesystem content-addressed store. Provider databases, object stores, Supabase, vector indexes, Bus projection, and Vera-specific integrations remain downstream adapters. Core importability cannot depend on them.

## Public Python interfaces

- `Ingestor.ingest(source, policy=None) -> IngestResult`
- `Ingestor.ingest_many(sources, policy=None) -> list[IngestResult]`
- adapter contract: `supports(source)` + `acquire(source, policy) -> Acquisition`
- `FileSystemStore` artifact/record/receipt/derivation operations

## CLI contract

Commands: `text`, `file`, `url`, `github`, `message`, and `inspect`.

Default output is compact machine-readable JSON on stdout. `--human` selects a compact human summary. `ACCEPTED` and `DUPLICATE` exit `0`; all other ingest result states exit `2`.

## V1 acceptance

V1 is acceptable when:

- identical bytes always have the same artifact SHA-256;
- identical source + bytes + parser semantics + policy resolve to the same ingest identity;
- repeat ingestion reports `DUPLICATE` without overwriting prior immutable records;
- different source identities can point to the same artifact without collapsing provenance;
- mutable GitHub refs are resolved to exact commits;
- invalid structured claims quarantine safely after raw preservation;
- event time and observation time remain distinct;
- receipts can be independently digest-verified;
- local tests pass from a clean package install.
