> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, commercial derivative products, and commercial model-training use require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

# ingest

**Ingest** is a provider-neutral universal intake boundary. It acquires heterogeneous inputs, preserves the exact raw bytes, creates deterministic normalized derivatives where appropriate, binds every artifact to provenance, and emits receipt-bearing records that downstream systems can consume without silently inheriting source-specific semantics.

The core rule is simple:

> **Acquire exactly. Preserve raw. Normalize explicitly. Hash deterministically. Keep provenance attached. Never promote intake into truth.**

## What V1 accepts

- inline text and bytes;
- local files with optional absolute-root confinement (CLI `--root` values are resolved to absolute paths before policy construction); raw local-file capture streams descriptor-bound chunks directly into the content-addressed store instead of first constructing one in-memory `bytes` payload;
- HTTP(S) resources with bounded streaming body capture, redirects, timeouts, validated-address connection pinning, and private-network denial;
- public/authenticated GitHub files through an injected transport, with mutable refs resolved to exact commits before acquisition; the default transport preflights exact blob metadata, streams raw Git blob bytes into CAS, recomputes Git object identity incrementally, and converts transport failures into governed acquisition failures;
- structured message/event envelopes where event time remains distinct from ingestion/observation time.

JSON and JSONL are deterministically canonicalized. UTF-8 text is normalized to NFC and LF line endings without whitespace stripping. Opaque binary data is preserved raw without pretending to understand it.

## What Ingest does not do

Ingest does not decide whether a claim is true, current, canonical, authoritative, independent, or semantically equivalent to another claim. It does not execute acquired code. It does not turn similarity into identity. It does not make a mutable Git branch name immutable provenance. Those are downstream responsibilities.

## Storage model

The default `FileSystemStore` is content-addressed. Interrupted writes can leave `.tmp-*` remnants; cleanup is explicit rather than automatic through `cleanup_stale_temp_files()`, which defaults to a 24-hour finite/non-negative age guard and reports reclaimed file/byte counts:

```text
.ingest/
  blobs/sha256/aa/<full-sha256>
  records/<ingest-id>.json
  receipts/<receipt-id>.json
  derivations/<derivation-id>.json
```

Raw and normalized artifacts are immutable. Artifact identity is SHA-256 of exact persisted bytes. Ingest identity is a canonical digest over stable source identity, raw SHA-256, parser-driving media type, normalizer version, and policy identity. Store reads are fail-closed: records recursively verify canonical JSON, receipt self-digests, derivation identity plus exact `normalize/PASS` parent?child receipt evidence bound to the same deterministic ingest identity, content-addressed blob metadata/bytes, and receipt/record cross-evidence before returning. Artifact size mismatches are rejected from the opened descriptor before blob bytes are read. Artifact digest verification and immutable collision checks are incremental rather than full-blob memory reads. The store also exposes bounded streaming publication for adapters. `ingest inspect` reports corrupted records as machine-readable `CORRUPT` with exit code `2` instead of returning unverified evidence. `ingest audit-records` deep-verifies every persisted record graph, accumulates corruption instead of stopping at the first bad record, and flags malformed or unexpected entries under `records/`. `ingest audit-store` inventories the full managed store, validates published blobs/receipts/derivations, and reports objects unreferenced by valid record graphs plus stale `.tmp-*` candidates without deleting anything.

This means identical bytes from different sources share a content artifact while retaining distinct ingest/provenance identities. Local-file acquisition binds bytes to an opened descriptor, streams raw chunks into durable staging/CAS publication, and rejects ordinary identity/size/timestamp changes across validation and read. During raw publication, local-file chunks also feed an incremental UTF-8/NUL/leading-token pre-sniffer. Definitive opaque/non-normalized inputs can therefore skip a post-capture full-blob read. JSON-looking streams can still materialize the verified raw artifact for exact generic media classification. JSONL/NDJSON normalization itself now reopens the verified raw CAS object as chunks and streams canonical derived bytes; general JSON and Unicode text normalization remain byte-oriented. Managed storage components below the configured store root reject symlink/junction redirection before creation, collision comparison, and publication. Concurrent first ingestion of the same identity is arbitrated by deterministic record semantics: one record wins, equivalent contenders resolve against it, and contradictory immutable content raises a store conflict instead of being accepted as a duplicate. For accepted ingests, the final `record/READY` receipt is bound into the immutable record; durable record presence is the acceptance commit point. On POSIX, newly created storage-directory entries are parent-synced as the store hierarchy is built, and new immutable publications also attempt to `fsync` the containing directory after the hard-link commit.

## Status model

- `ACCEPTED` — new material safely admitted and processed.
- `DUPLICATE` — the same deterministic ingest identity already exists in `ACCEPTED` state; repeated quarantined/partial material preserves the existing non-success status.
- `PARTIAL` — reserved for safe raw admission with incomplete optional derivations.
- `QUARANTINED` — raw bytes are preserved but structured downstream use is withheld.
- `REJECTED` — policy refused the material before durable artifact admission.
- `FAILED` — acquisition or internal processing could not produce a reliable admitted result.

## Python API

```python
from ingest import FileSystemStore, Ingestor, TextSource

store = FileSystemStore(".ingest")
ingestor = Ingestor(store)
result = ingestor.ingest(TextSource("hello", locator="urn:example:hello"))
print(result.status, result.ingest_id)
```

Batch ingestion is the same primitive repeated:

```python
results = ingestor.ingest_many([...])
```

## CLI

```bash
python -m ingest.cli text "hello"
python -m ingest.cli file ./record.json
python -m ingest.cli url https://example.org/data.json
python -m ingest.cli github OWNER REPO REF PATH
python -m ingest.cli message --id m-1 --source bus ./message.json
python -m ingest.cli inspect <ingest-id>
python -m ingest.cli audit-records
python -m ingest.cli audit-store
```

Machine-readable JSON is the default output. Use `--human` for a compact operator summary. `json` and `message` file/stdin reads are bounded by `--max-bytes` before parsing; malformed or non-object message input returns a machine-readable `REJECTED` result instead of an uncaught parser exit. Successful `ACCEPTED` and accepted-record `DUPLICATE` results exit `0`; repeated quarantined/partial records retain their non-success status and exit `2`.

## Provenance discipline

V1 incorporates mechanisms reviewed across Patrick's repository portfolio, especially Roots, Deep Memory Storage, Project Runner, SQL Connectome, Vera Mono, WorkBridgeMCP, Discovery, and World Zero. The original portfolio donor review is recorded in [`docs/PORTFOLIO_SOURCE_REVIEW_2026-09-25.md`](docs/PORTFOLIO_SOURCE_REVIEW_2026-09-25.md). The cross-domain capture/provider/orchestration donor review is recorded in [`docs/research/2026-09-29-donor-review-capture-gateways.md`](docs/research/2026-09-29-donor-review-capture-gateways.md). The implemented streaming acquisition boundary is specified in [`docs/architecture/STREAMING_ACQUISITION_V1.md`](docs/architecture/STREAMING_ACQUISITION_V1.md), and streaming normalization in [`docs/architecture/STREAMING_NORMALIZATION_V1.md`](docs/architecture/STREAMING_NORMALIZATION_V1.md). Store-audit semantics are specified in [`docs/architecture/STORE_AUDIT_V1.md`](docs/architecture/STORE_AUDIT_V1.md), with follow-on work in [`docs/ROADMAP.md`](docs/ROADMAP.md). Machine output contracts live under [`schemas/`](schemas/), including record, stage-receipt, record-audit, and whole-store-audit schemas.

The important boundary is that Ingest adopts **mechanisms**, not donor ontologies or conclusions. A receipt proves what Ingest observed and did. It does not prove what the content means.

## Verification

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

No runtime dependency is required beyond Python 3.12+ for V1.

## Status

`V0.1 SOURCE_IMPLEMENTED / LOCAL_VERIFICATION_PASS / NOT INSTALLED OR RUNTIME-CONSUMED`

Repository source, installation, runtime consumption, downstream provider effects, and independent review remain separate evidence domains.
