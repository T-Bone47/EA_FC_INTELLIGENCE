# Architecture decisions through the Phase 28 checkpoint

1. A registry decision authorizes an exact dataset release. Shared catalogue views expose a row only when its game version, entity scope, source and reviewed observation match an approved membership. Migration 011 establishes the storage contract and starts empty.
2. Application reads set the allowed release map inside a read-only PostgreSQL transaction. Candidate caching includes the environment and selected release map. Membership changes and revocation advance the database generation, so subsequent reads reflect committed changes.
3. Reviewed same-version player and card visibility applies independently. Linked records must pass their own scope gate. A card's attribute availability counts observed card-specific rows.
4. V3 resolves a formation assignment using existing slot definitions. It passes slot emphasis to the same demand computation used for eligibility, score and explanation. Position-only requests retain their existing scoring inputs.
5. The profile stores directly stated preferences. A user explicitly applies those values to a V3 form. The endpoint validates example styles and positions and preserves the existing profile preference container.
6. Legacy V2 surfaces remain isolated local tooling. The V3 parser covers the intents that can be represented safely as a structured draft.
