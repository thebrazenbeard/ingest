# Ingest continuation — 2026-09-29

Repository: `thebrazenbeard/ingest`  
Canonical branch: `main`  
Current `main`: `3116ae3f865fc4f430943772037f2fb8cc0dfd71`  
Current open hardening tip: `feature/stream-source-v1-20260929@d2d45c913ecb6ecfdc6770da2d0648b7ccd71cea`  
Tip tree: `9a07fd10c176c3f45ac6a22b1a7cc38647f3c587`

## Purpose

This file is the durable continuation point for the September 29 hardening/build run.

It distinguishes current `main` from the open Draft stack and records exact tested heads. Source in an open branch is not assumed to be merged, installed, activated, or runtime-selected.

## Current protected-effect boundary

Patrick remains the merge/protected-main authority.

The work below is repository preparation and review state only. No deployment, installation, provider activation, credential change, or runtime cutover is implied by these branches.

## Current Draft stack

The open chain is intentionally linear and each PR is mergeable.

1. PR #16 — **Integrate streaming and evidence hardening**
   - branch: `integration/hardening-v1-20260929`
   - head: `a07c540b26460c2a7bb797e00fff77249a13387a`
   - base: current `main@3116ae3f865fc4f430943772037f2fb8cc0dfd71`
   - GitHub Actions run #60: success
   - consolidates record/audit work already on main with local-file, HTTP, GitHub, storage, verification, streaming-pre-sniff, architecture, and roadmap hardening.

2. PR #17 — **Add read-only whole-store inventory audit**
   - branch: `hardening/store-inventory-audit-v1-20260929`
   - head: `37c02899fc2ba9fd06f798dfdf52618ed87ee4ac`
   - base: PR #16 head
   - run #61: success
   - adds `audit_store()` / `ingest audit-store`.
   - status model: `PASS | ISSUES | CORRUPT`.
   - reports unreferenced valid objects and stale temp candidates without deleting anything.
   - invariant: `UNREFERENCED != SAFE_TO_DELETE`.

3. PR #18 — **Add JSON schemas for audit outputs**
   - branch: `hardening/audit-schemas-v1-20260929`
   - head: `70a0a900ece717323dd0ca41e0c76b5aa36dc61f`
   - base: PR #17 head
   - run #62: success
   - adds explicit JSON schemas for `INGEST_RECORD_AUDIT_V1` and `INGEST_STORE_AUDIT_V1` with schema-surface tests and no runtime `jsonschema` dependency.

4. PR #19 — **Stream JSONL normalization from verified CAS**
   - branch: `hardening/jsonl-stream-normalize-v1-20260929`
   - head: `38bb57adc245b4566a56977d85f49e28185507b3`
   - base: PR #18 head
   - run #63: success
   - streams verified raw CAS chunks through incremental UTF-8/JSONL normalization into derived CAS.
   - preserves buffered V1 canonical output, line numbering, UTF-8 failure precedence, and `NORMALIZER_VERSION`.
   - JSON-looking classification can still require raw materialization.

5. PR #20 — **Restrict derived streaming to normalized artifacts**
   - branch: `hardening/derived-stream-boundary-v1-20260929`
   - head: `84a0148684f662fc201a53d2fea4ca4a065a05eb`
   - base: PR #19 head
   - run #64: success
   - removes the ability to route unbounded raw/source bytes through `put_derived_blob_stream()`.
   - derived unbounded streaming is normalized-only.
   - source streaming remains hard-bounded by mandatory positive `max_bytes`.

6. PR #21 — **Add caller-provided streaming source**
   - branch: `feature/stream-source-v1-20260929`
   - head before this continuation update: `d2d45c913ecb6ecfdc6770da2d0648b7ccd71cea`
   - base: PR #20 head
   - run #65: success
   - adds public `StreamSource(chunks, locator, media_type=None, source_identity={})` and default `StreamAdapter`.
   - caller byte iterables use the existing bounded streaming CAS path.
   - iterator/type/size failures are governed and do not publish completed raw blobs.
   - caller source identity is provenance only and cannot override artifact digest identity.

## Superseded Draft cleanup

The following stale Draft PRs were closed on 2026-09-29 after their surviving work was integrated into PR #16:

- PR #10 — bounded artifact verification / immutable collision reads;
- PR #12 — streaming local-file raw capture;
- PR #15 — streaming GitHub raw capture.

Their Git history remains intact. Closing them only removes ambiguous review paths.

## Exact verification at current tip

The exact PR #21 pre-continuation head `d2d45c913ecb6ecfdc6770da2d0648b7ccd71cea` was freshly checked through Workbridge on Windows.

Results:

- `py -m unittest discover -s tests -v`: **105 tests run, 104 passed, 1 expected Windows-only skip**;
- expected skip: POSIX directory-fsync probe;
- `py -m compileall -q src tests`: passed;
- `git diff --check`: passed;
- free disk observed during verification: approximately **116.9 GB**.

GitHub Actions run #65 is also green on Python 3.12 and 3.13 for that exact code head.

## Current architecture

### Stable identity boundaries

- raw artifact: SHA-256 of exact persisted bytes;
- ingest identity: canonical digest over stable source identity, raw SHA-256, parser-driving media type, normalizer version, and policy identity;
- derivations: explicit parent→child evidence with verified normalize receipts;
- Git commit identity, Git blob identity, artifact identity, ingest identity, and caller-provided source identity remain distinct.

### Streaming source/raw capture

The current open stack supports bounded raw streaming for:

- local files;
- default HTTP(S);
- default GitHub transport;
- caller-provided `StreamSource`.

All source/raw streaming uses a mandatory positive byte ceiling and exact persisted-byte hashing.

### Storage hardening

The current open stack includes:

- incremental SHA-256 verification instead of full-blob materialization for artifact verification;
- bounded immutable-collision verification;
- create-only CAS publication;
- fsynced staging and directory sync attempts;
- managed symlink/junction rejection;
- ctime-safe content verification;
- explicit stale-temp cleanup;
- read-time canonical/digest/cross-evidence verification.

### Audit surfaces

- `audit-records`: verifies persisted record graphs and unexpected `records/` entries;
- `audit-store`: inventories records, blobs, receipts, derivations, and temp candidates; distinguishes corruption from inventory issues;
- audit operations are read-only;
- schemas exist for both machine-readable audit outputs.

### Streaming normalization

JSONL/NDJSON normalization streams from verified CAS to normalized CAS while preserving V1 canonicalization semantics.

The unbounded derived-stream path is intentionally normalized-only.

## Claim ceilings that must remain explicit

1. **Repository source is not runtime activation.**
2. Unkeyed SHA-256/digests detect corruption and internal inconsistency but are not attacker-resistant authenticity if an actor can coherently rewrite the entire store.
3. Directory fsync is not portable on Windows; POSIX sync failures remain best-effort where the platform/filesystem rejects them.
4. Whole-store audit currently materializes inventory/reference sets in memory; it is not constant-memory for arbitrarily large stores.
5. The pipeline is not fully streaming for every media type. JSON-looking classification and ordinary JSON/text normalization can still require buffered materialization.
6. Automatic installed-plugin discovery remains rejected because it expands the trusted code surface and makes behavior installation-dependent.
7. Ingest is not a workflow engine. Scheduling, DAG execution, worker queues, approvals, SCADA control, model routing, and hardware control remain upstream.
8. A future capture/session identifier, if needed, must remain distinct from `artifact_id` and `ingest_id`.

## Donor research already preserved

The donor review is in:

`docs/research/2026-09-29-donor-review-capture-gateways.md`

It includes exact-head reviews of:

- microsoft/Qcodes
- ufrisk/LeechCore
- Velocidex/WinPmem
- PyMoDAQ/PyMoDAQ
- bluesky/bluesky
- jtsylve/LiME
- SCADA-LTS/Scada-LTS
- BerriAI/litellm
- intake/intake
- argoproj/argo-workflows
- windmill-labs/windmill
- rocketride-org/rocketride-server

The surviving cross-domain lessons are streaming/segmented exact-byte admission, adapter-owned provenance, small explicit adapter boundaries, recoverable acquisition without workflow-engine scope, and stable external references around immutable evidence.

## Recommended next frontiers

Work from the PR #21 tip unless the stack has since merged or moved. Fresh-read refs first.

### A. Incremental text normalization

Design a streaming text normalizer that preserves current V1 semantics exactly:

- strict UTF-8;
- CRLF/CR → LF;
- Unicode NFC normalization;
- no stripping;
- deterministic output;
- identity-visible normalizer version change only if semantics differ.

The difficult part is NFC across chunk boundaries; do not implement by normalizing chunks independently.

### B. Large JSON strategy

Do not claim streaming JSON until a deterministic strategy preserves exact canonical JSON semantics without unreasonable memory use. A full object model may inherently require substantial memory under current V1 rules.

### C. Constant-memory store audit

If needed for large stores, replace materialized reference sets/report arrays with sorted external/indexed traversal while preserving exact `PASS | ISSUES | CORRUPT` semantics.

### D. Optional advisory discovery

Only after concrete adapters justify it, consider:

`adapter.discover(source, policy) -> SourceDescriptor | None`

Discovery must remain bounded/advisory and must never replace acquisition-time validation.

### E. Acquisition-session recovery

Only if long-running sources demonstrate a real need. Keep the state machine limited to one evidence admission.

`CAPTURE_SESSION_ID != ARTIFACT_ID != INGEST_ID`

### F. External/object-store backend design

A future backend should preserve:

- exact content identity;
- create-only semantics;
- explicit integrity verification;
- raw/derived separation;
- auditability;
- provider-neutral core importability.

Do not convert provider presence into a runtime dependency of core Ingest.

## Resume procedure

1. Fresh-read `main` and open PRs; do not assume this file is current merely because it exists.
2. Identify the live tip of the linear Draft stack.
3. Verify CI and exact branch head before mutation.
4. Use a fresh isolated worktree for substantive code changes.
5. TDD behavior changes: establish red, implement minimum green, refactor, rerun full suite.
6. Run compile and diff checks.
7. Publish by non-force branch update and verify readback/CI.
8. Keep PRs Draft unless Patrick explicitly authorizes merge.
9. Close only clearly superseded/redundant Drafts; do not rewrite `main`.
10. Keep storage/temp cleanup bounded and avoid deleting unrelated model caches/venvs without proving they are disposable.
