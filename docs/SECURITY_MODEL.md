# Ingest V1 Security Model

## Trust boundary

Every acquired payload is untrusted data. V1 never executes, imports, evaluates, shells, deserializes with unsafe object loaders, or otherwise grants code authority to acquired bytes.

## Local files

Configured `allowed_roots` must be absolute paths and are resolved before use. Relative roots are rejected because the same policy digest could otherwise mean different filesystem authority under different working directories. Inputs resolving outside those roots are rejected. When link following is disabled, symlink/junction traversal is rejected across the full input path, not only at the final filename. File byte length is checked before and after reading.

## HTTP(S)

HTTPS is the default. Plain HTTP requires `allow_http=True`. Each requested/redirect URL is policy-checked, redirect count is bounded, reads are capped at `max_bytes + 1`, and a timeout is mandatory. A returned final URL is checked before its response body is consumed. Private, loopback, link-local, multicast, reserved, and unspecified destinations are denied by default.

The stdlib V1 transport performs hostname resolution checks before the request. This reduces ordinary SSRF risk but does **not** claim complete DNS-rebinding resistance because the HTTP stack may perform a second resolution. Production use against adversarial URLs should inject a transport that binds the validated IP/connection or delegates fetching to a hardened egress service.

Persisted HTTP provenance strips URL userinfo, query, and fragment from the human-readable locator. Exact requested/final URL distinctions remain bound by SHA-256 digests so credentials and secret query values are not written in plaintext.

## GitHub

Mutable refs are resolved to exact commits before content acquisition. The default GitHub API transport recomputes the returned file's Git object digest and rejects a blob identity that does not match the acquired bytes. Credentials are constructor/transport state and are never persisted in provenance objects or receipts. Exact commit/blob identity is evidence of source selection, not proof that repository content is safe or true.

## Structured parsing

JSON and JSONL use Python's data-only JSON parser and strict canonical serialization. Unsupported objects and non-finite numbers (`NaN`, `Infinity`, overflow to infinity) are not silently stringified or emitted as non-standard JSON. Claimed structured data that cannot be represented as strict JSON is quarantined after raw preservation; invalid structured message payloads are rejected before admission. No archive extraction is performed in V1, preventing archive-bomb/path-traversal classes from entering the core pipeline.

## Storage

Content blobs, records, receipts, and derivations are immutable create-only paths. A collision with different bytes/content raises a store conflict. First publication writes and fsyncs a temporary file, then uses a create-only hard link so an existing immutable path is never overwritten; the temporary path is removed afterward. Concurrent attempts for the same deterministic ingest/derivation identity may accept an already-created object only after checking its identity-defining fields; semantic conflicts still fail.

## Logging and secrets

V1 stores bounded structured errors, not tracebacks. Adapters must not place authorization headers, tokens, cookies, credentials, or secret query parameters into `SourceRef` or receipt details. Future redaction policy belongs before persistence, never as a promise that a stored secret can later be made un-stored.
