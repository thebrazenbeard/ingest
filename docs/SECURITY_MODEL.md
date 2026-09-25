# Ingest V1 Security Model

## Trust boundary

Every acquired payload is untrusted data. V1 never executes, imports, evaluates, shells, deserializes with unsafe object loaders, or otherwise grants code authority to acquired bytes.

## Local files

Configured `allowed_roots` are resolved before use. Inputs resolving outside those roots are rejected. Symlinks are rejected by default. File byte length is checked before and after reading.

## HTTP(S)

HTTPS is the default. Plain HTTP requires `allow_http=True`. Each requested/redirect URL is policy-checked, redirect count is bounded, reads are capped at `max_bytes + 1`, and a timeout is mandatory. Private, loopback, link-local, multicast, reserved, and unspecified destinations are denied by default.

The stdlib V1 transport performs hostname resolution checks before the request. This reduces ordinary SSRF risk but does **not** claim complete DNS-rebinding resistance because the HTTP stack may perform a second resolution. Production use against adversarial URLs should inject a transport that binds the validated IP/connection or delegates fetching to a hardened egress service.

## GitHub

Mutable refs are resolved to exact commits before content acquisition. Credentials are constructor/transport state and are never persisted in provenance objects or receipts. Exact commit identity is evidence of source selection, not proof that repository content is safe or true.

## Structured parsing

JSON and JSONL use Python's data-only JSON parser. Claimed JSON that cannot be parsed is quarantined after raw preservation. No archive extraction is performed in V1, preventing archive-bomb/path-traversal classes from entering the core pipeline.

## Storage

Content blobs, records, receipts, and derivations are immutable create-only paths. A collision with different bytes/content raises a store conflict. First publication writes and fsyncs a temporary file, then uses a create-only hard link so an existing immutable path is never overwritten; the temporary path is removed afterward.

## Logging and secrets

V1 stores bounded structured errors, not tracebacks. Adapters must not place authorization headers, tokens, cookies, credentials, or secret query parameters into `SourceRef` or receipt details. Future redaction policy belongs before persistence, never as a promise that a stored secret can later be made un-stored.
