# PHASE 23 — ENGINE RESULTS (Intelligence Evaluation Lab)

Measured 2026-09-30 with `scripts/run_intelligence_lab.py` (lab `lab-2026-09-30-r1`,
engine config `v3-2026-09-17-r1`). Raw JSON: `artifacts/phase23/lab/`.
Every number below was produced by running the production V3.1 engine; nothing was
re-tuned to make a number look better.

## Datasets

| | FC26 | FC27 |
|---|---|---|
| rows | 16,228 | 19,789 |
| data_status | CANONICAL | RESEARCH_ONLY (non-commercial snapshot) |
| reference distribution | `fc26-players-2026-09-r1` (frozen, hash `ac52f46d…`, rebuild verified IDENTICAL) | `fc27-players-2026-09-r1` (research dir, hash `224e4474…`) |
| divisions | men only | 17,849 men / 1,940 women |

## V3.1 baseline — per position (BALANCED counts; 6 tactical profiles)

Profiles: BALANCED, POSSESSION, HIGH_PRESS, LOW_BLOCK, COUNTER_ATTACK, DIRECT_PLAY.
"overlap" = mean pairwise top-10 overlap across the 6 profiles (lower = more tactical
discrimination). "opp" = HIGH_PRESS∩LOW_BLOCK / POSSESSION∩COUNTER_ATTACK top-10 overlap.

| GV | pos | overlap | opp | ρ(R,OVR) min–max | near-tie rate top-10 | missing-data violations |
|---|---|---|---|---|---|---|
| FC26 | CM | 5.93 | 3 / 6 | 0.73–0.93 | 0.76 | 360 / 2400 |
| FC26 | CDM | 5.93 | 4 / 8 | 0.89–0.95 | 0.76 | 324 / 2400 |
| FC26 | CAM | 4.87 | 4 / 6 | 0.77–0.96 | 0.87 | 340 / 2200 |
| FC26 | CB | 4.40 | 2 / 7 | 0.83–0.93 | 0.74 | 206 / 2800 |
| FC26 | LB | 5.53 | 3 / 7 | 0.71–0.93 | 0.63 | 167 / 2400 |
| FC26 | ST | 4.67 | 3 / 3 | 0.86–0.96 | 0.76 | 292 / 2800 |
| FC26 | LW | 5.33 | 3 / 6 | 0.79–0.91 | 0.72 | 177 / 2400 |
| FC26 | **GK** | **9.07** | **10 / 10** | **0.99–0.99** | 0.72 | 72 / 1000 |
| FC27 | CM | 5.93 | 5 / 6 | 0.75–0.93 | 0.81 | 319 / 2400 |
| FC27 | CDM | 5.73 | 4 / 6 | 0.87–0.92 | 0.76 | 295 / 2400 |
| FC27 | CAM | 4.93 | 4 / 5 | 0.78–0.95 | 0.91 | 323 / 2200 |
| FC27 | CB | 4.20 | 1 / 5 | 0.84–0.94 | 0.85 | 204 / 2800 |
| FC27 | LB | 5.53 | 2 / 6 | 0.73–0.93 | 0.74 | 176 / 2400 |
| FC27 | ST | 5.07 | 5 / 5 | 0.87–0.95 | 0.78 | 264 / 2800 |
| FC27 | LW | 4.93 | 4 / 6 | 0.81–0.91 | 0.85 | 150 / 2400 |
| FC27 | **GK** | **9.40** | **10 / 10** | **0.99–1.00** | 0.83 | 92 / 1000 |

Invariants, every position, both datasets (probe sample 200 real players; perturbed
copies are probes only):

| invariant | result |
|---|---|
| monotonicity (+1 on a demanded attribute) | **0 violations** (all positions) |
| Pareto (uniformly −3 copy never outscores) | **0 violations** |
| irrelevance (non-demanded attribute 1↔99) | **0 violations** |
| pool independence (alone vs in pool, 25 probes/pos) | **0 differences** |
| determinism (reversed + shuffled pool) | **identical ranking hash** |
| OVR independence (shuffle OVR across pool) | **identical ranking** — OVR is not a scoring channel |
| λ stability (0.70 → 0.65 top-10) | 10/10 at every position |
| evidence coverage κ | 1.00 at P01..P99 everywhere; NOT_EVALUABLE = 0 (κ_min gate still inert on player data) |
| **missing-data invariant** | **VIOLATED**: 3–15% of probes (F-1) |

## Findings

**F-1 — Missing information can make a player better (V3.1 defect, latent).**
C_lo charges an unpublished demanded attribute at the frozen P10. When a player's
published value is *below* P10, hiding it raises C_lo (max measured gain +0.0296 on FC27
CM — larger than most top-10 score gaps). Hiding a value ≥ P50 never helps (0
violations). Today every player publishes every demanded attribute (κ = 1.0), so
current rankings are unaffected; any partial-coverage entity (cards, future sources)
could exploit it.
Candidate fix `missing_value_charge = "ZERO"` (implemented in `capability_model.py`,
config field in `v3_config.py`, default still `"P10"`): **0 violations**, identical
rankings on both real datasets, all 65 V3 invariant/adversarial/hardening tests pass.
It changes 6 synthetic golden fixtures (partial-coverage scenarios) → requires an owner
decision + deliberate golden regeneration. **Recommendation: adopt as V3.2.**
A `P01` charge was also measured: fewer violations but not zero (65 on FC27 CM) → inferior.

**F-2 — Goalkeeper recommendations are tactically inert (V3.1 defect, active).**
GK demand is single-pole/magnitude-only over five collinear GK attributes. Result: the
GK top-10 is identical for HIGH_PRESS and LOW_BLOCK (10/10) and ρ(R,OVR)=0.99 — GK
recommendations are OVR sorting whatever the tactic.
Candidate H-GK-1 (signed two-pole GK demand; high line/press → positioning+kicking,
deep block → diving+reflexes+handling; only the five GK attributes FC26 also publishes;
`intelligence_lab.gk_signed_variant`):

| | FC26 base → H-GK-1 | FC27 base → H-GK-1 |
|---|---|---|
| mean overlap | 9.07 → **8.13** | 9.40 → **8.00** |
| HIGH_PRESS∩LOW_BLOCK | 10 → **7** | 10 → **6** |
| ρ min | 0.992 → 0.972 | 0.993 → 0.977 |
| top-10 median OVR (HP/LB) | 87/87 → 87/87 | 87/87 → 87/87 |
| near-tie rate | 0.72 → **0.81** | 0.83 → 0.80 |

High press now surfaces ter Stegen / Maignan / Hampton; low block surfaces Courtois /
Oblak / Donnarumma. By the pre-registered decision rule (near-tie rate must not rise) it
is REJECTED on FC26, adoptable on FC27. **Not adopted; owner decision.** The rule was
not changed after seeing the result. (`artifacts/phase23/lab/gk_experiment.json`)

**F-3 — Complementarity interaction (H-INT-1) rejected.** Monotone by construction and
invariant-clean, but tactical discrimination regressed on FC27 (+0.025 mean overlap)
and the near-tie rate rose on FC26 CM. Interaction modifier stays disabled.

**F-4 — Top-10s are dominated by near ties.** 63–91% of adjacent top-10 pairs are within
the 0.005 noise threshold. The API now exposes `near_tie_with_next` (gap, whether
within noise, whether intervals overlap, and the ScoringContext differential) instead
of implying a clear order.

**F-5 — OVR correlation is high but not a channel.** ρ 0.71–0.96 outfield (FC26 and FC27
alike) — structural (better players have better attributes). The OVR-shuffle test proves
exact independence. RD-3's 0.85 ceiling remains a policy question (unchanged).

**F-6 — Archetypes are separable in the real data.** Mean top-10 overlap between archetypes
sharing a position: CM 4.0 (FC26) / 3.5 (FC27); ST 4.7 / 4.3; CB 4.5 / 5.3; GK 7.0 / 6.0
(GK archetypes least separable, consistent with F-2). They are not used by V3; a V3.2
archetype demand stage would need its own lab run before any adoption.

**F-7 — FC27 differs from FC26 in ways the engine sees.** FC27 GKs publish all 29 outfield
detailed attributes (FC26 GKs: none), so the FC27 GK reference group has 34 attributes
vs FC26's GK-only set. FC27 mixes men's and women's divisions in one pool; the engine has
no division policy, so the API offers an optional, user-chosen `division` filter (no default).

## Decision rule (fixed before running)

A candidate is ADOPTABLE only if: monotonicity, Pareto and irrelevance have zero
violations everywhere; missing-data violations do not increase; mean tactical
discrimination does not regress; the near-tie rate does not rise.

| candidate | FC26 | FC27 | status |
|---|---|---|---|
| missing charge ZERO | ADOPTABLE | ADOPTABLE | recommended V3.2 — needs owner sign-off (6 synthetic goldens move) |
| missing charge P01 | ADOPTABLE | ADOPTABLE | dominated by ZERO (not zero violations) |
| complementarity (H-INT-1) | REJECTED | REJECTED | discarded |
| GK signed poles (H-GK-1) | REJECTED (near-tie rule) | adoptable | owner decision |

## V3.1 defaults — unchanged

λ = 0.7, PlayStyle Model A, interaction modifier disabled, confidence reporting-only,
no OVR channel, ranking on C_lo, κ logic, missing charge P10. Config version unchanged.

## Tests / regression

Full suite: **24 failed / 662 passed / 1 skipped** — the 24 failing IDs are identical to
the Phase 22/23 baseline (9 v2 history, 11 pre-existing integration, 4 RD-3/RD-4 policy).
New: 29 adapter tests + 58 Phase 23 version-wall/API tests. Mutation checks: removing the
engine reference guard, serving research rows by default, or letting the licence gate
accept a production override each make a Phase 23 test fail (3/3 caught).
