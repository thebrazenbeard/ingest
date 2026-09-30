# Store Audit V1

Status: IMPLEMENTED ON HARDENING LINE
Date: 2026-09-29

## Purpose

`audit-store` is a read-only inventory and integrity surface for the filesystem store. It answers a different question from `audit-records`:

- `audit-records`: are the persisted record graphs valid?
- `audit-store`: what published objects exist across every managed namespace, which are reachable from valid record graphs, and which structural/integrity problems are present?

The command never deletes, rewrites, quarantines, or repairs evidence.

## Report contract

Schema: `INGEST_STORE_AUDIT_V1`

Statuses:

- `PASS` ? published managed objects and structure validate, with no stale temp candidates or valid unreferenced objects.
- `ISSUES` ? no corruption was established, but valid objects are unreferenced by valid record graphs and/or stale `.tmp-*` files were observed.
- `CORRUPT` ? at least one published object or managed namespace failed structural/integrity verification.

Only `PASS` is a successful CLI exit (`0`). `ISSUES` and `CORRUPT` exit `2`.

## Inventory boundary

The audit enumerates:

- `records/*.json`;
- `receipts/*.json`;
- `derivations/*.json`;
- `blobs/sha256/<prefix>/<digest>`;
- store-owned `.tmp-*` files.

It also rejects unexpected entries or link-like substitutions inside managed namespaces.

Published blobs are verified by exact filename SHA-256, prefix placement, byte count, managed-path controls, and incremental content hashing. Receipts, derivations, and records use their normal fail-closed read verifiers.

## Reachability

Reference sets are derived only from **valid record graphs**. A valid record contributes:

- raw and normalized artifact IDs;
- record receipt IDs;
- derivation IDs;
- the normalization receipt referenced by each valid derivation.

Valid published objects absent from those reference sets are reported as `unreferenced_*`.

`UNREFERENCED != SAFE_TO_DELETE`

A record may have been externally deleted or corrupted; an interrupted higher-level operation may also leave valid evidence without a record. The audit intentionally reports reachability, not disposal authority.

## Temporary files

`.tmp-*` files are recognized as store-owned staging residue. Recent temp files are counted but do not by themselves change status because a concurrent writer may still own them.

A temp file older than `stale_after_seconds` (default 24 hours) is reported in `stale_temp_files` and produces `ISSUES`, not `CORRUPT`.

Deletion remains an explicit separate action through `cleanup_stale_temp_files()`.

## Corruption examples

`CORRUPT` includes:

- a record whose deep graph verification fails;
- a receipt or derivation whose canonical identity/digest fails;
- a blob whose bytes do not match its SHA-256 pathname;
- symlink/junction substitution of managed namespaces or objects;
- malformed/unexpected managed directory entries.

## Concurrency and claim ceiling

Published objects use create-only paths, so the audit can safely verify completed entries while concurrent writers stage `.tmp-*` files. A completed object that disappears or mutates during audit is reported as corruption/inconsistency.

V1 store audit is O(number of managed entries) and materializes ID/reference sets plus issue lists in memory. It is suitable for the current filesystem-store scale but does not yet claim constant-memory reporting over arbitrarily large stores.

The audit detects internal corruption and inconsistency. It is not cryptographic authenticity against an actor with full store write access who can coherently rewrite objects and recompute unkeyed hashes.
