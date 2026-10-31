# Ingest

**Provenance-bound data intake for Python applications and evidence pipelines.**

Ingest is a Python library and command-line tool for acquiring untrusted material from different kinds of sources, retaining the exact bytes received, and producing content-addressed artifacts, normalized derivatives, provenance records, and verifiable stage receipts. It gives downstream systems a consistent intake record without deciding whether the material is true, trustworthy, authoritative, or semantically equivalent to other content.

Version `0.1.0` is implemented as local source and tests. This repository does **not** supply a hosted ingestion service, an installed cross-system integration, or a host authorization service.

## What it can ingest

| Source | Implemented boundary |
| --- | --- |
| Text and bytes | Inline text or binary payloads with caller-defined locators. |
| Streams | Caller-provided byte iterables through `StreamSource`, bounded by policy before admission to the content-addressed store. |
| Local files | Descriptor-bound, size-limited reads; optional absolute-root confinement and symlink controls. |
| Web resources | HTTP(S) downloads with limits for size, redirects, and timeouts; private-network destinations denied by default. |
| GitHub files | Public or authenticated acquisition through the adapter transport; mutable refs are resolved to commit identity, with default blob verification. |
| Messages and events | JSON object envelopes that preserve the distinction between source/event time and ingestion time. |

JSON and JSONL have deterministic canonicalization; UTF-8 text is normalized to Unicode NFC and LF line endings. Raw bytes are retained independently of normalized output. Unknown binary formats are stored as opaque data, not guessed into structures.

## Quick start

Requires **Python 3.12 or newer**. From a checkout:

```bash
python -m pip install .

# Record an inline text source in a local store.
ingest --store ./ingest-data --human text "sample evidence" --locator urn:example:sample

# Verify the managed content-addressed store without deleting anything.
ingest --store ./ingest-data --human audit-store
```

The first command reports an ingest status and identifier; the audit reports record, blob, receipt, and integrity counts. `--store` selects where records are stored. The same input and policy can produce `DUPLICATE` on later admission, while preserving provenance and deterministic identity semantics.

The CLI also exposes `file`, `url`, `github`, `json`, `message`, `inspect`, and `audit-records` commands. For example:

```bash
ingest --store ./ingest-data file ./sample.json
ingest --store ./ingest-data inspect INGEST_ID
```

Replace `INGEST_ID` with the identifier from a successful ingestion. `url` acquisition follows HTTP policy controls; do not enable private-network access for untrusted callers.

### Python API

```python
from ingest import FileSystemStore, Ingestor, IngestPolicy, StreamSource, TextSource

ingestor = Ingestor(FileSystemStore("./ingest-data"))

record = ingestor.ingest(
    TextSource("sample evidence", locator="urn:example:sample")
)
print(record.status, record.ingest_id)

# Source adapters may supply chunks without buffering the entire payload first.
stream = StreamSource(
    [b"part one\n", b"part two\n"],
    locator="urn:example:stream",
    media_type="text/plain",
)
stream_record = ingestor.ingest(stream, policy=IngestPolicy(max_bytes=1024))
print(stream_record.status)
```

Applications may use `BytesSource`, `FileSource`, `UrlSource`, `GitHubFileSource`, and `MessageSource` as well. The public exports are in [`src/ingest/__init__.py`](src/ingest/__init__.py); policy settings are in [`src/ingest/policy.py`](src/ingest/policy.py).

## Artifacts, records, and verification

The default [`FileSystemStore`](src/ingest/storage.py) stores raw and derived blobs under SHA-256 content identities, with separate ingest records, derivations, and stage receipts. Multiple source records may refer to identical blob bytes without losing their separate source identity. Ingest rejects conflicting immutable records and fails closed when persisted evidence fails integrity checks.

The CLI reports `ACCEPTED`, `DUPLICATE`, `PARTIAL`, `QUARANTINED`, `REJECTED`, or `FAILED`. `PARTIAL` is reserved for optional-derivation incompleteness; duplicate non-success records retain their original status. `inspect` verifies a stored record before returning it, and `audit-records` and `audit-store` examine stored evidence without automatic deletion.

For field contracts and detailed behavior, see:

- [Machine-readable schemas](schemas/README.md)
- [Security model and threat boundaries](docs/SECURITY_MODEL.md)
- [Streaming acquisition design](docs/architecture/STREAMING_ACQUISITION_V1.md)
- [Streaming normalization design](docs/architecture/STREAMING_NORMALIZATION_V1.md)
- [Store audit contract](docs/architecture/STORE_AUDIT_V1.md)
- [Roadmap and non-goals](docs/ROADMAP.md)

## Trust and security limits

Ingest treats every input as untrusted data; it does not execute acquired code. Policies bound byte size and supported network/file access. The default HTTP transport checks address resolution and connects to validated addresses, but custom transports are responsible for their own connection binding. File metadata checks narrow races; they do not create a formal filesystem snapshot guarantee.

**A valid receipt proves what this local process recorded and checked, not that a remote provider told the truth.** Ingest does not attest external provider identity, establish host-owned authority, grant consent, adjudicate evidence, run workflows, or authorize downstream effects. Integrators must enforce those boundaries independently.

The tracked VS Code configuration does not auto-run a task when the repository opens. A concealed folder-open launcher was removed from the active tree and is covered by an editor-startup regression test; historical source remains in Git history. The repair is not evidence that the launcher ever executed.

## Test and development

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

CI exercises the suite on Python 3.12 and 3.13. Tests establish behavior of the repository's implementation; they do not prove deployment into another system. The source test suite may open a temporary loopback HTTP listener during redirect tests.

## License

**Source-visible, proprietary; not open source.** The repository grants limited noncommercial review and research rights under [`LICENSE`](LICENSE). Commercial use, redistribution, public derivative distribution, and commercial model-training use require separately documented permission; see [`COMMERCIAL_LICENSE.md`](COMMERCIAL_LICENSE.md). Third-party material retains its own licenses.
