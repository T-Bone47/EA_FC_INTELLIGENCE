# PHASE 21 RELEASE DECISION

## Outcome

**OUTCOME C/D — UNVERIFIED / BLOCKED across all providers.** No provider has supplied explicit written rights. No controlled pilot is authorized. This is reported as the honest result of the investigation, not as a shortfall — Outcome A (a verified pilot) was never achievable within this session, because it requires a real response from a third party this system cannot solicit and receive within a single conversation. Preparing to ask correctly, and refusing to fabricate an answer, is the actual deliverable.

## Final decision matrix

| Provider | Access | Automate | Store | Derive | Commercial | Display | Redistribute | Retain | Card IDs | Prices | PlayStyles | Roles | **Overall** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FutDB (futdb.app) | ALLOWED | SILENT | SILENT | SILENT | AMBIGUOUS | SILENT | SILENT | SILENT | n/a | n/a | n/a | n/a | **PARTIAL** |
| FUT-DB.com | ALLOWED | CONDITIONAL | SILENT | SILENT | ALLOWED | SILENT | **PROHIBITED** | SILENT | n/a | n/a | n/a | n/a | **BLOCKED** |
| FUTBIN | ALLOWED (human) | **PROHIBITED** | PROHIBITED | PROHIBITED | PROHIBITED | PROHIBITED | PROHIBITED | SILENT | n/a | n/a | n/a | n/a | **BLOCKED** |
| FUTWIZ | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | n/a | n/a | n/a | n/a | **UNVERIFIED** |

Card IDs / Prices / PlayStyles / Roles are marked `n/a` for every provider because **no pilot data was ever ingested from any of them** — there is nothing to evaluate at the field level yet. This is distinct from marking those fields UNKNOWN, which would imply an attempt to check them; none was possible without ingesting data no provider has authorized.

Every cell above traces to `artifacts/phase21/provider_rights_matrix.json`, which cites the specific terms-of-service section or "NO_EVIDENCE_SUPPLIED" for each answer — no cell was filled from memory or assumption.

## Why FutDB.app reads PARTIAL rather than BLOCKED

Unlike FUTBIN (explicit, absolute prohibitions across almost every dimension) or FUT-DB.com (an explicit redistribution prohibition), FutDB.app has never explicitly prohibited anything — it has simply never published terms that address any of these questions at all. `PARTIAL` here reflects "one dimension (access) is clearly fine, everything else is genuinely unknown, not refused" — which is meaningfully different from a hard block, even though the practical effect (do not ingest) is identical today. This distinction is exactly why direct outreach to FutDB.app, if a contact channel can be found, is the single most promising remaining path: there is no existing prohibition to negotiate around, only silence to resolve.

## What would change this decision

Any provider supplying `EXPLICITLY_ALLOWED` for all six minimum-production dimensions (access, automation, storage, derivation, commercial, display) — see `MINIMUM_PRODUCTION_DIMENSIONS` in `provider_license_evaluator.py` — moves that provider to `VERIFIED`, and only then does Outcome A (a controlled 10–50 card pilot) become authorized. Raw-data redistribution rights are explicitly **not** required for this, since the product serves derived recommendations, not a raw-data mirror (Phase 21 §11) — this is why FUT-DB.com's specific redistribution prohibition is worth a direct, narrow clarifying question rather than treating it as an automatic dead end.

## What remains true regardless of outcome

```
entity_scope = "game_player" only, unchanged, enforced at the API schema type level
UT-card recommendation: disabled
V3.1 scoring: byte-for-byte unchanged (lambda=0.7, PlayStyle Model A,
              interaction modifier disabled, golden fixtures identical)
Zero fabricated cards, zero access-control bypass, zero unauthorized outreach sent
```
