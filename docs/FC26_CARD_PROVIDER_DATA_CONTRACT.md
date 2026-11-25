# FC26 CARD PROVIDER DATA CONTRACT

Minimum field contract for a pilot, once (and only once) explicit rights are obtained from a provider.

## Required identity fields

| Field | Requirement | Notes |
|---|---|---|
| `source_card_id` | **required** | The provider's own card identifier. Never derived from name+OVR (identity-collision risk established in `FC26_IDENTITY_RESOLUTION_SPEC.md`) |
| `source_player_id` | **required** | Must be distinct from `source_card_id` — a player has many cards |
| `game_version` | **required** | Must be exactly `"FC26"`; anything else (or absent) is rejected at the version wall |
| `card_version` | **required** | Distinguishes a re-issued/upgraded card from the original |
| `card_type` | **required** | Base, TOTW, promo, Icon, Hero, Evolution, etc. — used for canonical identity, never inferred from OVR or rarity colour |

## Required football fields, where the provider actually supplies them

| Field | Requirement | Notes |
|---|---|---|
| `overall` | required if available | |
| `positions` (primary + secondary) | required if available | |
| detail attributes (29 fields, per `card_model.DETAIL_ATTRS`) | required if available | Missing values stay `NULL`, never defaulted |
| `club`, `league`, `nation` | required if available | |

## Optional fields — supported by the schema, never blocking a pilot if absent

| Field | Requirement | Notes |
|---|---|---|
| PlayStyles (base) | optional | Recorded as an observed fact only; `playstyle_data_published` flag distinguishes "none held" from "not reported" |
| PlayStyle+ | optional | Same discipline |
| Roles | optional | No source has ever supplied this at any legal status across all sessions; the field exists, unpopulated |
| `price`, `price_timestamp` | optional | Modelled as a `card_price_observation`, never as card metadata (Phase 21 S18); never enters the v3 capability score |

## What is deliberately NOT required

Chemistry, Evolution lineage details beyond a version link, and any gameplay-effect coefficients for PlayStyles or Roles are not required for a pilot and are not requested from any provider in this phase's outreach materials — the product does not need them to demonstrate a working, licensed ingestion pipeline, and requesting them would invite exactly the kind of invented-coefficient risk this project has repeatedly ruled out.

## Field-level legality carries independently of this contract

A field being present in this contract does not mean it is automatically publishable. Every field must separately clear the license gate (`GREEN`) before being served — see `artifacts/phase21/license_evidence.json` and `card_publication_gate.py`. A provider could grant rights to attributes and positions while withholding rights to price, and the pilot would then publish the former and withhold the latter, per-field, exactly as `FC26_DATA_QUALITY_SPEC.md`'s original field-level legality design intended.
