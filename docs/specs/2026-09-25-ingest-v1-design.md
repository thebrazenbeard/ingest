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

`observed_at` never substitutes for an event timestamp supplied by source evidence. For HTTP(S), persisted human-readable URL provenance excludes userinfo, query, and fragment; SHA-256 digests bind the exact requested/final URLs without storing likely credentials or secret query material in plaintext.

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

- strict parse and strict JSON serialization;
- non-finite numbers are rejected/quarantined rather than emitted as `NaN`/`Infinity`;
- unsupported Python objects are never silently stringified;
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

A repeated observation does not promote the disposition of the existing record: an accepted existing record yields `DUPLICATE`, while an existing quarantined/partial record preserves that non-success state and is marked as a duplicate observation in warnings/receipts.

## GitHub provenance

A requested branch or tag is a mutable acquisition hint. The GitHub adapter resolves it to an exact commit before reading file content, and `SourceRef.source_identity` binds owner, repository, exact commit, and path. The default API transport recomputes the returned file's Git object digest and rejects a reported blob identity that does not match the acquired bytes. The originally requested ref remains claimed metadata. When the transport does not supply a media type, the repository path provides the same extension-based structured-type hint used for local files (`.json`, `.jsonl`, and other standard mimetypes), so invalid structured files do not silently degrade into plain text solely because they came from GitHub.

Credential material belongs to the transport object, not the source record, receipt, locator, or artifact.

## Security boundary

V1 requires:

- no acquired-code execution;
- hard input byte ceilings;
- local allowed-root confinement when configured, with absolute roots required for unambiguous policy identity;
- full-path symlink/junction denial by default unless link following is explicitly enabled;
- HTTPS by default;
- HTTP only by explicit policy;
- bounded redirects;
- required network timeouts;
- private/loopback/link-local network denial by default;
- raw preservation before structured parsing when admission is safe;
- no automatic archive/container extraction.

The default HTTP(S) transport binds each connection to an address that passed the private-network policy check, so a later hostname re-resolution cannot silently redirect that connection onto a forbidden network. HTTPS certificate verification still uses the original hostname. Injected custom openers remain supported, but they own their own connection-binding guarantee.

## Storage boundary

V1 ships a filesystem content-addressed store. Provider databases, object stores, Supabase, vector indexes, Bus projection, and Vera-specific integrations remain downstream adapters. Core importability cannot depend on them.

Concurrent same-identity ingestion is first-writer-wins only after verifying identity-defining fields. Equivalent races resolve to the already-created record/derivation; a true immutable-content conflict still raises `StoreConflict`.

## Public Python interfaces

- `Ingestor.ingest(source, policy=None) -> IngestResult`
- `Ingestor.ingest_many(sources, policy=None) -> list[IngestResult]`
- adapter contract: `supports(source)` + `acquire(source, policy) -> Acquisition`
- `FileSystemStore` artifact/record/receipt/derivation operations

## CLI contract

Commands: `text`, `file`, `url`, `github`, `json`, `message`, and `inspect`.

Default output is compact machine-readable JSON on stdout. `--human` selects a compact human summary. CLI-side `json` and `message` file/stdin reads obey `--max-bytes` before parsing, and malformed/non-object message input is returned as a governed machine-readable rejection. `ACCEPTED` and `DUPLICATE` exit `0`; all other ingest result states exit `2`.

## V1 acceptance

V1 is acceptable when:

- identical bytes always have the same artifact SHA-256;
- identical source + bytes + parser semantics + policy resolve to the same ingest identity;
- repeat ingestion reports `DUPLICATE` without overwriting prior immutable records;
- different source identities can point to the same artifact without collapsing provenance;
- mutable GitHub refs are resolved to exact commits and default-transport Git blob identity is byte-verified;
- invalid structured claims quarantine safely after raw preservation;
- event time and observation time remain distinct;
- receipts can be independently digest-verified;
- local tests pass from a clean package install.
