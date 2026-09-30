# Ingest continuation — 2026-09-30

Repository: `thebrazenbeard/ingest`  
Canonical branch: `main`  
Status: repository-source work, not installation or runtime activation.

## Fresh-bound repository state

At the start of the September 30 continuation, `main` was
`9c1a514f5140c89c0eb5c3c6fda5f9744436b25f`.

PR #22 (**Integrate streaming and evidence hardening**) was already merged. Its integration ancestry incorporates the formerly divergent source work without dropping the audit/donor branch. Do not merge that work a second time.

The subsequent open Draft development stack is:

- PR #17: read-only whole-store audit.
- PR #18: record/store audit JSON schemas.
- PR #19: streaming JSONL normalization from verified CAS.
- PR #20: normalized-only derived stream publication.
- PR #21: caller-provided `StreamSource` using bounded raw CAS admission.
- PR #23: HTTP error response cleanup and managed-record `ctime` race correction (stacked on #21).

PR #16 is an older Draft integration branch; assess its changed content against the already merged PR #22 before any future integration or closure. PRs #17–21 remain stacked across earlier branch ancestry rather than all targeting current `main`. Their status is not evidence that their source is installed or selected by a running Vera system.

## Work performed this continuation

1. Re-read current `main`, PR topology, and the latest PR #21 commit `db3541aa9474307f8b9a42080266f54440a9e9b4`.
2. Checked the full latest stacked source in isolated worktree `C:\Temp\ingest-next-20260930`. The initial 105-test run was green but raised a Python 3.14 `ResourceWarning` for an unclosed synthetic HTTP 302 response.
3. Added a failing test proving `HTTPError` responses were not closed on redirect follow, redirect-limit rejection, or terminal HTTP errors.
4. Updated `HttpAdapter._open_validated_response()` to close the caught HTTP response in `finally`; focused and full local tests turned green.
5. Published verified source as Draft PR #23, first remote commit `46b6970733655447abd666aa4c36216bb8f181b7`.
6. GitHub Actions #69 exposed a separate existing Python 3.13 concurrent-ingest failure: a record JSON read rejected hard-link-induced `ctime` drift despite unchanged bytes.
7. Added a deterministic failing patched-`fstat` test, changed generic managed-object read stability to device/inode/size/mtime, preserved canonical JSON, record/receipt cross-evidence and blob SHA-256, and updated `docs/SECURITY_MODEL.md`.
8. Stress-ran the concurrent-ingest test **80 consecutive times**, no failures; the full local suite ran **107 tests (106 passed; one expected Windows-specific POSIX-fsync skip)**. Compilation and Git diff checks passed.
9. Published the second exact-tree-checked remote commit `9be6b32d6af16ac3f64544623e433880dd270d03`, tree `d014c0fb05b871a8d3dcd13c715bf2c407ff59f0`.
10. GitHub Actions run **#70 passed Python 3.12 and Python 3.13** at that code head.

The final continuation document itself may create a newer documentation-only PR head. Always resolve the live branch ref and exact CI result before citing a newer head as verified.

## Evidence and claim ceilings

**REPOSITORY_SOURCE:** GitHub branch refs, PR state, content, commits, and published Git object trees.

**RUNTIME_OBSERVATION:** Local Python tests exercised the source in a Workbridge worktree; no evidence of `vera_core.QualifiedVeraRuntime` installation, route selection, continuous operation, or runtime ingestion was established.

**EXTERNAL_VERIFICATION:** GitHub Actions ran Linux Python 3.12/3.13 against the published source.

**NOT ESTABLISHED:** cryptographic authenticity against a fully privileged rewriting attacker, universal power-loss durability, or complete constant-memory processing of every input class.

## Next bounded work

1. Fresh-read `ingest/main` plus PRs #16–23 before edits.
2. Verify PR #23's current head, CI, and stacked base; keep Draft unless explicit merge authorization names that exact target.
3. Build a clean reviewable integration candidate for the still-open #17–21 feature stack from current `main`, preserving independently merged source rather than copying an older tree wholesale. TDD and cross-platform CI must precede a merge proposal.
4. Expand source/derived stream tests around aborted iterators, caller-supplied identity claims, size ceilings, JSONL chunk boundaries, and preservation of exact raw evidence.
5. Treat stale temporary files and unreferenced store objects as audit findings, not automatic deletion authority.
6. Keep device/workflow scheduling, arbitrary plugin activation, provider mutations, deployment, and credentials outside core Ingest and outside this continuation's authority.

## Protected-effect boundary

Patrick authorized the earlier integration merge; it is already represented by merged PR #22. This continuation does **not** extend that authorization to merging the remaining Draft PRs, changing `main` directly, deploying/installing runtimes, changing credentials, deleting arbitrary files, or activating providers. Draft preparation, isolated testing, comparison, and review remain in scope.
