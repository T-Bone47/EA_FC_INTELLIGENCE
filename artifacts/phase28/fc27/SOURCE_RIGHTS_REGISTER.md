# FC27 source rights register

The active external data budget is ₹0. Commercial feed assessments below are historical. The current card workflow uses the local FC27 item research release and leaves prices unavailable. [Current engineering status](../../phase29/ZERO_BUDGET_STATUS.md)

| Source | Observed use decision | Production scope |
| --- | --- | --- |
| Pinned September player CSV | Existing Phase 22 local, non-commercial research | None |
| GitHub player CSV copy | Forensic duplicate evidence | None |
| October statistics and identity table | Owner-supplied local staging with unknown reuse rights | None |
| Card item table | Owner-supplied local staging with unknown reuse rights | None |
| FCData | Public documentation review | Awaiting provider permission |
| FUT-DB | Public FC27 OpenAPI contract reviewed | API key and written permission for the intended data uses pending |
| DataFluxor FUT Data | Public API and terms reviewed | Product display is advertised. Confirm project-specific storage, derivation, and downstream rights before use. |
| EA FC Community API | Official partner programme reviewed | Account-data access for approved partners |

The local PostgreSQL staging command cannot enroll its observations in the serving catalogue. The existing player ingestion binds its complete hash-pinned snapshot to the existing research-only release, subject to the source clearance and version firewall.

## External FC27 feeds reviewed on 23 November 2026

| Source | Documented fit | What to verify with a sample and written terms |
| --- | --- | --- |
| FUT-DB | The FC27 schema exposes distinct `resourceId` and `resourceBaseId` fields, detailed outfield and goalkeeper attributes, alternative positions, PlayStyles/PlayStyles+, and Roles/Role++. The provider advertises a free API key and reserves some fields for premium access. [API specification](https://api.futdatabase.com/api/doc/v1/swagger.json), [provider and plan details](https://app.futdatabase.com/). | First choice for an evaluation sample for V3.2. Verify item and base ID meanings and field coverage across multiple versions of the same player. Confirm permission to retain snapshots, compute and publish derived recommendations, and display or expose card fields. Section 7 requires explicit permission for reproduction, distribution, or modification. [Terms](https://fut-db.com/terms). |
| DataFluxor FUT Data | The feed documents EA item IDs, player IDs, rarity, face stats and timestamped PC and console prices. FUT Flipper advertises the same DataFluxor API. [Product documentation](https://datafluxor.com/fut-data), [FUT Flipper API page](https://futflipper.com/price-api). | Candidate for identity checks and market prices. Detailed scoring attributes and PlayStyles coverage need confirmation. The advertised product-display permission limits resale of raw API access, and the provider terms assign EA compliance to the subscriber. Confirm caching, release retention, derivation and downstream display separately. [Provider terms, section 10](https://datafluxor.com/terms). |
| FCData | The site describes in-game stats, PlayStyles, roles and timestamped prices. [About](https://fcdata.io/about/). | A supported feed or export and a written reuse scope remain unconfirmed. The existing request is ready for owner review. [Terms](https://fcdata.io/terms), [request draft](FCDATA_PERMISSION_REQUEST_DRAFT.md). |
| EA FC Community API | Account connections for FUTBIN, FUT.GG, and FUTWIZ. EA says it is currently closed to new requests. [EA announcement](https://www.ea.com/games/ea-sports-fc/news/pitch-notes-fc26-community-api-update), [EA Help](https://help.ea.com/en/articles/ea-sports-fc/community-api/). | The published programme covers account-data access through approved sites. The documentation does not offer a bulk card catalogue export for this project. |

The evaluation sample should include a goalkeeper, a base outfield item and two special versions of the same player. Check the provider's item IDs against Archive 4 `stats_id` and Archive 5 `eaId` with ratings, club, and rarity recorded as corroboration. Measure detailed attribute coverage before building a card reference. Confirm the meaning and provenance of roles separately from the editorial role-fit values in Archive 5.

This review verified public documentation. Live payloads, upstream permissions, and execution against either API await access and an explicit evaluation scope.
