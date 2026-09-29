# Ingest donor review — capture, run, provider, and catalog systems

Date: 2026-09-29  
Evidence class: EXTERNAL_EVIDENCE, exact-head pinned  
Target: `thebrazenbeard/ingest`  
Research branch base: `hardening/filesystem-durability-v1@48789cd58ac0f54c787b5a13e48bd500e6acdce3`

## Scope and claim ceiling

This review studies mechanisms in nine external repositories supplied for Ingest research. These repositories are donor/reference systems only. They are not runtime dependencies, installation evidence, provider bindings, or authority to copy implementation. No donor source code is incorporated by this document.

The question is narrower: which cross-domain mechanisms improve Ingest's provider-neutral acquisition, provenance, identity, integrity, and future large/streaming-source support without turning Ingest into a laboratory framework, SCADA scheduler, memory acquisition driver, or LLM gateway?

## Exact donor bindings

| Repository | Exact default-branch head |
| --- | --- |
| `microsoft/Qcodes` | `main@4b1af10f2af2a25c0f59c8b1194c405f00c69933` |
| `ufrisk/LeechCore` | `master@7436c5e9720c7bc816260f29c705332197ea286d` |
| `Velocidex/WinPmem` | `master@f59d776a3defc6aa869fdcb0bbe3aafe39ee1a55` |
| `PyMoDAQ/PyMoDAQ` | `5.2.x@d996fc9681397f20634d60f903fb70cc4c99a879` |
| `bluesky/bluesky` | `main@cc5e48c768c3642f777a3a1e4c3dba6f2fe91970` |
| `jtsylve/LiME` | `master@7511bffe797df9d87ae4db853ef123745cc5bc2c` |
| `SCADA-LTS/Scada-LTS` | `develop@f1cf088585cabd6f5a457698a764e0fc07cf98ee` |
| `BerriAI/litellm` | `main@d46304900f283f34226a5021935efe67de6730b5` |
| `intake/intake` | `master@1eab92ce49c56a6c37ea9b409c04ae6cb894454a` |

## Cross-domain conclusions

Three mechanisms survive across these otherwise very different systems.

1. **Provider/device/source complexity belongs behind an adapter boundary.** LeechCore, Intake, LiteLLM, SCADA-LTS, PyMoDAQ, and QCoDeS all isolate source-specific behavior instead of letting it infect every downstream consumer. Ingest already has the right primitive: injected adapters with `supports()` and `acquire()`. The next improvement should strengthen explicit registration/discovery contracts, not add source-type conditionals to the core pipeline.

2. **Acquisition semantics need richer provenance, but not a premature core ontology.** Memory acquisition systems distinguish live/volatile versus file-backed sources, QCoDeS distinguishes snapshot freshness, Bluesky separates run/session metadata from individual documents, and PyMoDAQ preserves producer origin and timestamps. Ingest should be able to preserve volatility, snapshot/session identity, segmentation/range structure, and capture consistency when an adapter knows them. V1 should carry these as adapter-owned structured provenance rather than introducing a hard-coded global enum before multiple real adapters require one.

3. **Large, segmented, and streaming sources are the real architectural frontier.** WinPmem and LiME expose physical ranges; LeechCore spans volatile devices and dump files; Bluesky emits document streams; Intake models partitions/chunks. Ingest's current whole-buffer `bytes` acquisition is intentionally simple but will not scale to memory images, long scientific runs, or large partitioned sources. The future design should add bounded incremental hashing/persistence and optional segment manifests without changing the rule that raw artifact identity is SHA-256 of exact persisted bytes.

## Donor-by-donor findings

### QCoDeS

Observed mechanisms:

- `Metadatable.snapshot()` makes snapshot freshness explicit through canonical modes `All`, `Only_invalid`, and `Never`.
- Dataset/run attributes retain run timestamps, completed timestamps, metadata, parent dataset links, a run description, and a captured snapshot.
- Run identity and snapshot state are distinct concepts.

Transfer to Ingest:

- Preserve adapter-declared snapshot/freshness semantics in provenance when applicable.
- Preserve parent/session/run lineage as source metadata rather than pretending it is content identity.
- Keep observation time separate from source/capture time, consistent with the existing message/event boundary.

Do not transfer:

- Instrument/parameter object models belong to acquisition adapters or downstream scientific tooling, not the Ingest core.

Useful exact-head source:
- `src/qcodes/metadatable/metadatable_base.py`
- `src/qcodes/dataset/data_set_info.py`

### LeechCore

Observed mechanisms:

- One handle-based API abstracts dump files, live memory, hardware acquisition, remote acquisition, and external device plugins.
- Device configuration exposes source/device distinctions and volatility.
- Core consumers do not need source-specific read logic after a device is opened.

Transfer to Ingest:

- Continue the adapter-neutral core.
- Preserve source volatility/live-vs-snapshot semantics when an adapter can state them.
- Treat remote/local transport and device method as provenance, not as a reason to fork the pipeline.

Do not transfer:

- Auto-loading external native plugins into the core.
- Write-capable memory/device operations.
- Remote command execution or agent control.
- Hardware-specific configuration in Ingest schemas.

Useful exact-head source:
- `includes/leechcore.h`
- `leechcore/leechcore.c`

### WinPmem

Observed mechanisms:

- The kernel side exposes physical memory ranges and system memory information.
- Userspace is responsible for richer imaging behavior such as copying, networking, and hashing.
- Physical memory is not assumed to be one semantically homogeneous interval; the acquisition surface exposes ranges.

Transfer to Ingest:

- Keep privileged/source-specific capture outside the persistence/evidence core.
- For segmented sources, preserve a range/segment manifest as provenance or a derivative while keeping the raw captured representation exact.
- Preflight declared segment/size metadata before large reads where possible, but never let discovery replace acquisition-bound verification.

Do not transfer:

- Kernel-driver lifecycle, privileged acquisition methods, or OS-specific memory semantics into core Ingest.

Useful exact-head source:
- `src/userspace_interface/winpmem_shared.h`
- `src/winpmem.c`
- `site/content/docs/memory.md`

### PyMoDAQ

Observed mechanisms:

- Data objects distinguish `raw` versus `calculated` source classes.
- Data carries timestamp, labels, origin, dimensional/distribution metadata, and axes where applicable.
- Saving and loading are designed symmetrically around typed data objects.

Transfer to Ingest:

- Preserve producer origin and producer/capture timestamp separately from ingestion observation time.
- Continue distinguishing direct source material from derived/normalized material through explicit derivation evidence.
- A future structured/segmented adapter may emit a manifest describing dimensions or channels, but those domain fields should remain adapter-owned.

Do not transfer:

- Axes, detector, actuator, GUI, or HDF5-specific concepts into the generic record schema.

Useful exact-head source:
- `packages/pymodaq_data/src/pymodaq_data/data.py`
- `packages/pymodaq_data/src/pymodaq_data/h5modules/data_saving.py`
- `docs/src/data_management/saving_loading_data.rst`

### Bluesky

Observed mechanisms:

- `RunEngine` executes plans and emits documents rather than forcing all run state into one object.
- Run metadata can be validated and normalized before a run starts.
- Persistent run metadata is separate from individual events.
- The document model distinguishes run-level and event/resource-level evidence.

Transfer to Ingest:

- Model future run/session intake as linked records/documents, not as one giant synthetic blob.
- Preserve a source session/run identifier and document sequence in adapter provenance when ingesting event streams.
- Consider bounded metadata validation before accepting a stream/session descriptor.

Do not transfer:

- Plan execution, device orchestration, pause/abort state machines, or scheduling. Ingest admits evidence; it should not become the experiment executor.

Useful exact-head source:
- `src/bluesky/run_engine.py`
- `src/bluesky/bundlers.py`

### LiME

Observed mechanisms:

- The LiME memory format places a small versioned header before each memory range.
- The header binds magic/version and explicit start/end addresses for the following range.

Transfer to Ingest:

- Prefer explicit versioned segment manifests for segmented acquisition rather than implicit byte-position conventions.
- Preserve segment ordering and source-range identity independently from the global raw artifact digest.

Do not transfer:

- A LiME-specific header or physical-address schema into the generic core.

Useful exact-head source:
- `src/lime.h`
- `docs/README.md` (LiME Memory Range Header Version 1)

### SCADA-LTS

Observed mechanisms:

- Source-specific runtime classes encapsulate protocol behavior.
- Point locators describe source-specific address semantics.
- Polling cadence and point updates are acquisition/runtime concerns, not storage concerns.

Transfer to Ingest:

- Continue allowing adapters to own locator grammar and source-specific configuration.
- Normalize acquisition failures at the adapter boundary.
- If continuous SCADA intake is ever needed, place polling/scheduling outside Ingest and submit bounded observations into Ingest.

Do not transfer:

- Polling loops, point runtime state, control/write operations, alarms, or SCADA lifecycle into the Ingest core.

Useful exact-head source:
- `src/com/serotonin/mango/rt/dataSource/*DataSourceRT.java`

### LiteLLM

Observed mechanisms:

- Many providers are normalized behind a common interface.
- Provider resolution is partly registry/config driven.
- Provider-specific failures are mapped into common failure classes.
- Routing/fallback policy sits above provider adapters.

Transfer to Ingest:

- Keep provider/source registration explicit and separate from pipeline semantics.
- Continue converting adapter/network/provider exceptions into bounded governed acquisition failures.
- Prefer data/config-driven registration for families of equivalent adapters only when it does not execute arbitrary code.

Do not transfer:

- Model routing, retry/fallback selection, spend/load balancing, or a giant provider catalog into core Ingest.
- Provider inference must never silently change evidence identity.

Useful exact-head source:
- `litellm/litellm_core_utils/get_llm_provider_logic.py`
- `litellm/types/router.py`

### Intake

Observed mechanisms:

- A small `DataSource` interface separates source description/discovery from full reads.
- Driver implementations expose metadata, partitioning, schema/discovery, read/read-chunked, and close lifecycle.
- Driver initialization is expected to remain lightweight.
- Plugins can extend source support without changing the core.
- Intake explicitly notes that consumer/destructive sources such as FIFO queues do not fit assumptions designed for reopenable/readable data.

Transfer to Ingest:

- A future optional adapter discovery/preflight contract is useful for large sources, but its output must remain advisory and acquisition must revalidate anything security- or identity-relevant.
- Partition/chunk semantics should inform the future streaming acquisition design.
- Adapter registration should remain explicit/injected in V1; plugin loading should not happen merely because a package is installed.
- Destructive/consumer streams need a different acquisition contract from replayable files/URLs.

Do not transfer:

- Automatic entrypoint plugin execution in the minimal core.
- Container/dataframe abstractions that belong downstream of raw evidence admission.

Useful exact-head source:
- `intake/source/base.py`
- `docs/source/making-plugins.rst`
- `docs/source/catalog.rst`

## Hostile review

> **HOSTILE REVIEWER:** These repositories are large domain systems. A "capabilities" schema copied from them would make Ingest an ontology project instead of a reliable intake boundary.

**Accepted.** No generic source-capability enum should be added yet. Adapter-owned structured provenance is sufficient until at least two or three concrete new adapters require the same field to affect policy or identity.

> **HOSTILE REVIEWER:** Intake and LiteLLM show plugin/registry systems, so Ingest should auto-discover installed adapters now.

**Rejected as a V1 change.** Automatic discovery expands the trusted code surface and makes behavior depend on environment installation state. Explicit adapter injection is more deterministic and auditable. A future registry may describe explicitly enabled adapters without automatically importing arbitrary installed plugins.

> **HOSTILE REVIEWER:** Memory/scientific systems imply streaming, but adding streaming now could destabilize the already-working exact-byte identity model.

**Partially accepted.** Streaming is a real requirement, but it needs a design that preserves exact byte hashing, bounded reads, create-only persistence, crash semantics, and deterministic receipts. Design first; do not bolt an iterator onto `Acquisition.data` and call it done.

## Recommended follow-on work

### 1. Design bounded streaming persistence before adding large-source adapters

Define a streaming acquisition contract that:

- incrementally enforces `max_bytes`;
- hashes exact bytes incrementally;
- writes to a durable temporary artifact;
- publishes create-only only after final digest is known;
- never requires holding the full artifact in memory;
- preserves the existing SHA-256 artifact identity and receipt model;
- can surface partial/acquisition failure without mislabeling incomplete bytes as a complete artifact.

This is the highest-value cross-domain lesson from WinPmem, LiME, LeechCore, Bluesky, and Intake.

### 2. Define an optional advisory source-discovery contract

Potential shape:

`adapter.discover(source, policy) -> SourceDescriptor | None`

The descriptor may report bounded metadata such as estimated size, replayability, volatility, partition count/range summary, source session identity, and media hints.

Rules:

- discovery is optional;
- discovery must be bounded;
- discovery output is provenance/advisory unless the acquisition step revalidates it;
- discovery must not become a TOCTOU authority boundary;
- secrets remain subject to the same provenance redaction rules.

### 3. Standardize adapter-owned acquisition provenance before promoting fields to core schema

Candidate concepts seen repeatedly across donors:

- source/capture session identifier;
- source volatility/replayability;
- snapshot/freshness mode;
- capture consistency claim;
- segment/range summary;
- producer/source event time;
- adapter/device method.

Keep them namespaced or adapter-owned until repeated real use demonstrates a core invariant.

### 4. Keep scheduling, control, routing, and execution outside Ingest

SCADA polling, Bluesky plan execution, LiteLLM routing/fallback, LeechCore remote execution, and hardware/device control are all deliberately out of scope. Upstream systems may perform those actions and submit resulting observations to Ingest.

### 5. Preserve raw-versus-derived evidence explicitly

PyMoDAQ's raw/calculated split reinforces the existing Ingest direction: raw admitted bytes and normalized/derived products must remain distinguishable and linked by explicit derivation evidence. Future transforms should extend derivation semantics rather than mutating raw artifacts in place.

## Decision

The donor review does **not** justify a new runtime dependency or immediate schema expansion.

It does justify two future design tracks:

1. **streaming/segmented acquisition with incremental exact-byte persistence**, and
2. **optional bounded source discovery plus richer adapter-owned acquisition provenance**.

Until those designs are proven against the existing identity, receipt, crash-durability, and read-verification contracts, the current small injected-adapter core remains the stronger architecture.
