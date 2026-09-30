# Ingest JSON Schemas

These schemas describe stable machine-readable persistence and operator-output contracts.

- `ingest-record-v1.schema.json` ? persisted ingest records.
- `ingest-stage-receipt-v1.schema.json` ? persisted pipeline stage receipts.
- `ingest-record-audit-v1.schema.json` ? `audit-records` output.
- `ingest-store-audit-v1.schema.json` ? `audit-store` inventory/integrity output.

Schema identifiers use the emitted `schema` discriminator (for example `INGEST_STORE_AUDIT_V1`) rather than a network URL. V1 has no runtime JSON-Schema dependency; tests load these files with the standard library and compare required surfaces against real emitted payloads.

The schemas document shape. They do not independently prove semantic validity, integrity, or authenticity; those checks remain in the Ingest verifier and storage contracts.
