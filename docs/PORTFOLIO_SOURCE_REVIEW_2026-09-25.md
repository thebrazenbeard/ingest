# Portfolio Source Review — Ingest V1

Date: 2026-09-25
Scope: every repository accessible under `thebrazenbeard` at review time.
Inventory count: **69 repositories including the initially empty `ingest` repository**.

This was a mechanism-admission review, not a claim that sibling repositories become runtime dependencies. Every donor remains provenance/reference material unless code is explicitly copied or a future integration binds it.

## Admitted mechanism donors

| Repository | Exact reviewed head | Mechanism admitted | Boundary preserved |
| --- | --- | --- | --- |
| `roots` | `2c591176279d83ce6cc0d8dcf8e6062431913ea7` | source locator/time discipline; ingestion time ≠ event time; evidence vs inference; provenance gaps remain gaps | Ingest does not perform Roots lineage/origin interpretation |
| `deepmemorystorage` | `fe73b7eee2e8b2498ff994c57e46080de329a0ef` | stable event/content fingerprints, source-frontier digests, append-only ingest receipts, anti-collapse rules | no autobiographical/canonical-memory semantics imported |
| `project-runner` | `8aa5da0f55cd029e9cf4da79a090aa50859e662a` | canonical fingerprinting; discovery/provenance path does not define underlying identity; registry snapshot SHA-256 | no scheduling/worker ontology imported |
| `sql-connectome` | `66ed8e00ab04fcb6080c7a1362304601d00edafe` | canonical JSON + digest-bound receipts | no SQL-dialect ontology imported |
| `vera-mono` | `895ca6cd147bb5f21115eb9ff609e52f4fe231af` | exact-source verification discipline; explicit failure/admission states; source/runtime/effect separation | no Vera runtime authority or identity semantics imported |
| `WorkBridgeMCP` | `8707a2e1eaf7de5ce2316567b5e6f1e805c0537b` | exact donor-head/blob admission, adaptation rules, rejected carryovers, claim ceilings | no process-execution authority imported |
| `discovery` | `368e8dc8274e89a306039d28462c7547b263e93e` | minimal interchange below project ontology; shared record cannot promote truth/currentness/authority | no universal semantic ontology created |
| `world-zero` | `4cf0e094ebc6d4792f9dac9b3e0798a4307edf87` | subject identity bound to exact source/digest sets and execution receipts | no scientific model/claim semantics imported |

Additional useful portfolio patterns were screened in `wreckforge` (archive inventory/hash/source traceability), `selfimage` (registration state distinct from binary acquisition state), `driftguard` (receipt/trust claim boundaries), `hc-brain` (source ancestry/evidence custody), `vera-control-plane` (source manifests/currentness), and `vera` (provider/source registries and receipt-first replay safety). They informed pressure testing but add no V1 runtime dependency.

## Complete repository screening inventory

The following repositories were all checked at their then-current default-branch README/surface. `DONOR` means a concrete V1 mechanism was admitted above or materially pressure-tested. `SCREENED` means no additional V1 mechanism was admitted after review.

```text
vera DONOR
vera_ark SCREENED
build-team-2.0 SCREENED
vera_model_training SCREENED
project-lantern SCREENED
chat-communication-bus SCREENED
vera-os SCREENED
vera-apk SCREENED
vera-synology SCREENED
vera-mesh SCREENED
vera-habitat SCREENED
project-achilles SCREENED
vera-R9A0 SCREENED
voss SCREENED
hephaestus SCREENED
masamune SCREENED
vera-control-plane DONOR
trek-data-core SCREENED
hc-brain DONOR
selfimage DONOR
deepmemorystorage DONOR
semanticatlas SCREENED
conations SCREENED
empathy SCREENED
vera-works SCREENED
brigit SCREENED
skeletonkey SCREENED
entropyinc SCREENED
spm SCREENED
sexuality SCREENED
brigit-unbound SCREENED
wip SCREENED
mediaphile SCREENED
bugops SCREENED
noema SCREENED
abil SCREENED
unvtrslr SCREENED
personification SCREENED
temporal SCREENED
conditioning SCREENED
self SCREENED
bt2 SCREENED
orgasm SCREENED
Attune SCREENED
wreckforge DONOR
rezon SCREENED
roots DONOR
world-zero DONOR
on-theo SCREENED
firesafe SCREENED
project-runner DONOR
intranel SCREENED
transcendence SCREENED
mosaic SCREENED
testament SCREENED
driftguard DONOR
discovery DONOR
god-brain SCREENED
WorkBridgeMCP DONOR
meso-crct SCREENED
unbound-sol SCREENED
RepairTracker SCREENED
freerowcochkar SCREENED
ccb-core SCREENED
fuckup SCREENED
vera-mono DONOR
sql-connectome DONOR
axle SCREENED
ingest TARGET / EMPTY AT REVIEW START
```

The authoritative inventory count is 69 repositories including `ingest`.

## Admission rule used

A donor pattern was admitted only when it could live below downstream project ontology and did not silently convert retrieval into admission, provenance into truth, source into runtime state, or content similarity into identity.

## Claim ceiling

`PORTFOLIO_WIDE_SOURCE_SCREEN_COMPLETE / SELECTED_MECHANISMS_ADMITTED / NO_SIBLING_RUNTIME_DEPENDENCY`
