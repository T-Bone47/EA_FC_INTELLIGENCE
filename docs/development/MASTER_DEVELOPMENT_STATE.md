# EA FC Intelligence development state

## Phase 30 local card squad release

Open the FC27 research card explorer and follow **Open Ultimate Team Squad Lab**. The local release supports exact shortlisted item assignment, roster locks, formation changes, tactical alternatives, upgrades, saved scenarios and signed item feedback. See [the Phase 30 engineering report](../../artifacts/phase30/FINAL_ENGINEERING_REPORT.md) for tested scope and outstanding release decisions.

## Phase 28 checkpoint

The Phase 27 inspection and the Phases 27–32 master directive guided this checkpoint. The local workspace is an exported source tree. The change archive includes hashes and an application patch against the inspected Phase 27 tree.

| Workstream | Checkpoint outcome |
| --- | --- |
| Phase 27 release boundary | Migration 011 binds shared catalogue access to reviewed records in an explicitly permitted release. Scoped reads fail closed if the views are absent. Existing release decisions stay in effect. |
| Phase 28 tactical intelligence | The V3 studio supports formation assignments. Recommendations, comparisons and what-if requests use the same slot-aware demand composition. Score and eligibility use the existing model. |
| Phase 28 player preferences | Accounts can store a stated default position and tactical style and explicitly apply them in the studio. |
| Phase 28 intent drafts | V3 validates the existing parser's supported output as a draft and identifies unsupported requests. The studio currently uses structured controls. |
| Phase 29 cards | Card browsing reports gated availability. Released identities and attributes are counted independently. Variant comparison, verified market data, role assignments, chemistry rules and Evolutions remain open. |
| Phases 30–32 | The existing squad CRUD, evidence views and feedback routes remain in the application. V3 squad analysis, replacements, optimization, deeper personalization and release certification remain open. |

## Resume in the workspace

1. Apply migration 011 using the existing tracked setup on a clean disposable PostgreSQL 16 instance. Exercise the mixed-release fixture before approving any membership workflow.
2. Build a release-scoped card comparison path on the existing card repository. Use isolated fixtures for known attributes and incomplete evidence. Keep visibility, price timestamp and missing-data cases in the contract.
3. Bring formation-aware player scoring into the existing squad builder and test an owned squad end to end. Add a deterministic replacement objective before introducing an optimizer.
4. Run the hosted browser pipeline from an actual revision. Record deployment evidence only after approved data, calibration and regression gates are resolved.

See [the feature matrix](FEATURE_COMPLETION_MATRIX.csv), [open decisions](OPEN_DECISIONS.md), [blockers](KNOWN_BLOCKERS.md) and [test index](TEST_EVIDENCE_INDEX.md).

## FC27 integration extension

The owner-supplied FC27 source audit and runtime checks are indexed in
[the FC27 engineering report](../../artifacts/phase28/fc27/FINAL_ENGINEERING_REPORT.md).
The release-bound local FC27 snapshot has a browser-tested search and squad flow.
The October and card-oriented tables have a separate append-only staging ledger.
Fixture-backed card comparison and scoring share the existing V3.2 capability model.
Card activation awaits a licensed source, reviewed row membership and a frozen
card reference. Follow the FC27 feature matrix for remaining product and release gates.
