# API wiring

- Overview uses `/api/meta/game-versions`, `/api/v3/options`, owner-scoped `/api/squads`, and `/api/saved-players`. Checking the local card release is a separate opt-in GET.
- Discover uses the existing player, card, facets and detail APIs. FC27 local inventory filters run server-side before pagination. The new detail route looks up one exact canonical item UUID inside the existing authorized research pool.
- Intelligence Studio uses `/api/v3/recommendations`, `/api/v3/compare`, `/api/v3/what-if` and feedback. Submitted settings stay attached to the returned result. The compatibility recommendation workflow is still routed separately.
- Card comparisons use the exact-item local compare and alternate-tactics routes. The public player comparison and permitted-card catalogue retain their existing contracts.
- Squad Lab calls the existing preview, transform and saved-scenario endpoints. The pitch displays draft assignments or an explicitly labelled optimized preview. Draft edits and undo invalidate the pending pitch generation. Save uses the backend receipt.
- Evidence Lab uses the Phase 31 cohort, item, compare, submissions and review endpoints. Publication and game-version rules follow the backend release gate.
