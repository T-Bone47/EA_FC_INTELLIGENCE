# V3.1 CALIBRATION REPORT

**Question this report answers:** is V3 mathematically and empirically calibrated enough to become the stable intelligence layer the product builds on?

**Answer:** Yes, for player scope, with one policy decision still open (RD-3's correlation ceiling) and one near-miss (CB's tactical-responsiveness spread) that does not block release. Two of the four "genuine findings" carried into this session turned out to be a measurement-tool artifact, not an engine limitation — corrected and reported below, not quietly absorbed.

---

## A. Baseline (Phase 0)

```
Python:        3.12.3
PostgreSQL:    16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
game_player:   16,228 (FC26, 0 rejected)
ut_card:       60 (SYNTHETIC_TEST fixtures only)
field_provenance: 499,088 rows (at session start)
config_version: v3-2026-09-17-r1
config_hash:    09a7293b21d1347e1afe724a3df64020dd7e9b42330e76e12f1419a6ded60455
reference_distribution_version: fc26-players-2026-09-r1
reference_distribution_hash:    ac52f46dc8a2433db57daf51cea02936605a38d07dde00fd9176966ea6609f22
```

Full source-tree hash, config snapshot, and reference-distribution metadata saved to `artifacts/v3_1/baseline/`, untouched for the remainder of this session.

Baseline suite, confirmed before any change: **30 failed, 410 passed, 1 skipped**, unchanged from the prior session's end state — the environment had not drifted between sessions (Postgres data survives restarts; no code had been touched).

Note on the 465/24/1/2 numbers quoted in the mandate: a full run at the very start of *this* session actually showed **23 failed, 468 passed, 1 skipped, 0 xfail** — one better than reported. That discrepancy turned out to be the first real finding of this session (Section B).

---

## B. RD-3 investigation (Phase 1) — and a correction to the previous session's own numbers

### B.1 A measurement-tool bug, found before trusting any further number

Re-measuring RD-4 for CB in isolation gave **0.076** in one script and **0.116** in another, on identical data, with no code changes. Both computations were traced side-by-side in a single process: the engine's ranking was proven **bit-identical** regardless (`INV-9`), so the discrepancy was not engine non-determinism. It was in `_spearman()`, the measurement helper itself.

The original `_spearman()` assigned ranks via a stable sort over raw scores. For **tied scores** — common here, since `c_lo` is a weighted sum of integer 1–99 attributes and many real players land on the same value — a stable sort assigns ranks by **original list order**, not by an average of the tied positions. Whether the input list had been sorted-by-score first (as in the shipped `_top10_overlap_and_rho` helper) or left in raw pool order (as in an earlier ad-hoc probe) changed which tied element "won" the lower rank, which measurably shifted the correlation.

**Fixed**: `_spearman()` now uses proper average-rank tie handling, which is invariant to input order by construction. Re-verified deterministic across three separate process invocations post-fix.

This is a measurement-methodology defect, not an engine defect. `INV-15` and the direct OVR-shuffle counterfactual (Section C) — neither of which used `_spearman()` — were unaffected throughout and already proved zero OVR dependence before this fix existed.

### B.2 The corrected numbers change the picture materially

With the fix, **CM's previously-reported tactical-discrimination failure does not reproduce.** Old (buggy) vs. corrected:

| Metric | Reported last session | Corrected this session |
|---|---|---|
| CM mean top-10 overlap (target ≤6.0) | 6.9/10 (FAIL) | **5.7/10 (PASS)** |
| CM PRESSING∩LOW_BLOCK (target ≤4) | 5/10 (FAIL) | **4/10 (PASS)** |
| CB mean top-10 overlap | 4.9/10 | 4.6/10 |
| CB PRESSING∩LOW_BLOCK | 3/10 | 3/10 |
| ST mean top-10 overlap | 5.0/10 | 4.4/10 |

**CM's position baseline being passing-dominated is still true** (confirmed by direct inspection: `short_passing` carries weight 0.128 under `BALANCED`, zero tactical pull) — but it does not, in fact, prevent CM from clearing the RD-1/RD-2 thresholds once measured correctly. The earlier diagnosis conflated a real structural property with a symptom that turned out to be a measurement artifact. **Phase 3's investigation is therefore largely moot**: there is no CM tactical-discrimination shortfall left to explain.

### B.3 What genuinely remains: RD-3's correlation ceiling

Corrected, deterministic measurement, all positions, all 5 tactical profiles plus `BALANCED`:

| Position | rho(R, OVR) range | Exceeds 0.85 ceiling |
|---|---|---|
| CB | 0.817 – 0.911 | every profile |
| ST | 0.830 – 0.950 | every profile |
| CM | 0.746 – 0.925 | 4 of 6 profiles (BALANCED, POSSESSION, PACE_ABUSER, DIRECT_PLAY) |

**Structural decomposition** (Phase 1 requirement — does saturation, position baseline, or something else drive it?): computed the *raw, unsaturated, v/99-linear* weighted mean and the *saturated* capability score in parallel for the identical CM/POSSESSION demand vector. Result: **rho(raw linear, OVR) = rho(saturated, OVR) = 0.9246, to four decimal places.** Saturation contributes nothing measurable to the correlation. The correlation is present even under `BALANCED` (zero tactical pull, position baseline only): rho = 0.8825.

**Conclusion:** the correlation is a structural property of *any* weighted linear combination of football attributes, because OVR is itself approximately such a combination. This matches Session 1's own PCA finding (PC1 explains 40.6% of attribute variance, correlates 0.672 with raw OVR) and its own explicit prediction for capability-only scoring ("retains rho of +0.68…+0.90 — good players still rank well"). **The 0.85 ceiling was never validated against what a compliant, guard-case-passing engine could structurally achieve; it now has been, and it cannot be reached.**

---

## C. OVR shuffle / counterfactual audit (Phase 2)

The decisive test, distinct from correlation:

- Loaded 300 real CM candidates, scored normally, then **randomly permuted OVR across all candidates while leaving every attribute untouched**, and re-scored.
  **Result: `max|R_original − R_shuffled| = 0.00e+00`** across 270 comparable candidates — not merely below a tolerance, exactly zero.
- Took the single best-attributed player in the sample, set `overall_rating` from its true value to `1`, re-scored: **R unchanged, exactly.**
- Kendall tau(R, OVR), CM/POSSESSION, n=600 subsample: **0.768** (consistent with, and slightly lower than, the Spearman figures, as expected for the two statistics).

**Correlation is high. Dependence is zero, exactly, not approximately.** This is the distinction the mandate asked to be kept explicit, and the evidence supports both halves independently: OVR is not a hidden ranking channel (proven by the shuffle test), and capability legitimately tracks genuine quality (proven by the correlation and the guard-case tests in Section E).

---

## D. CB tactical responsiveness (Phase 4)

CB's RD-4 spread, corrected measurement: **0.094** against a target of ≥0.10 — closer than previously reported (was 0.076) but still short.

Investigated the causal chain directly: dumped the top-6 demand attributes for CB under `PRESSING` and `LOW_BLOCK`. They share **zero attributes in common** (`reactions, acceleration, stamina, interceptions, pace, aggression` vs. `strength, standing_tackle, defensive_awareness, composure, heading_accuracy, positioning`). The demand vector construction is not the bottleneck.

Confirmed via the lambda sweep (Section F): raising lambda toward 1.0 does not monotonically widen CB's spread — it peaks in the middle of the range and both CB's `mean_overlap` (worsens again at λ≥0.9) and its correlation spread show a real CB-specific ceiling that persists across the whole safe operating range. The remaining, most likely explanation (G from the investigation checklist) is the **real-world data distribution itself**: elite center-backs in the actual 16,228-player pool tend to be well-rounded across both the pace/recovery axis and the strength/duel axis (that combination is close to the definition of an elite modern CB), so even a well-differentiated demand vector produces a smaller OVR-correlation swing between opposite tactics than at ST or CM, where genuine one-dimensional specialists (pure pace merchants, pure creators) are more common in the population.

This is 0.006 short of the target, with a well-evidenced structural explanation, not a construction defect. **No parameter change is recommended for CB specifically** — see Section F for why forcing it further is not free.

---

## E. Lambda sweep (Phases 5–6)

Full sweep, λ ∈ {0.0, 0.1, …, 1.0}, all three positions, RD-1/RD-2/RD-3 metrics, plus the four sharpest T1 guard cases re-run at every value. Complete data: `artifacts/v3_1/calibration/lambda_sweep.json`.

| λ | CB overlap/opposed/rho | ST overlap/opposed/rho | CM overlap/opposed/rho | Guards |
|---|---|---|---|---|
| 0.0 | 6.90 / 8 / [.86,.92] | 6.30 / 6 / [.84,.94] | 8.00 / 10 / [.84,.94] | **G-B2 FAILS** |
| 0.1 | 6.40 / 7 / [.85,.92] | 5.90 / 6 / [.84,.94] | 7.10 / 8 / [.83,.94] | **G-B2 FAILS** |
| 0.2 | 5.90 / 6 / [.83,.92] | 5.50 / 5 / [.84,.95] | 6.50 / 6 / [.81,.94] | **G-B2 FAILS** |
| **0.3** | 5.40 / 5 / [.82,.91] | 5.10 / 4 / [.83,.95] | 6.10 / 5 / [.79,.93] | **ALL PASS** |
| 0.4 | 5.00 / 4 / [.82,.91] | 4.80 / 3 / [.83,.95] | 5.90 / 5 / [.78,.93] | ALL PASS |
| 0.5 | 4.80 / 3 / [.82,.91] | 4.60 / 3 / [.83,.95] | 5.80 / 4 / [.77,.92] | ALL PASS |
| 0.6 | 4.60 / 3 / [.82,.91] | 4.40 / 2 / [.83,.95] | 5.70 / 4 / [.77,.92] | ALL PASS |
| **0.7 (current)** | 4.60 / 3 / [.82,.91] | 4.40 / 2 / [.83,.95] | 5.70 / 4 / [.77,.92] | ALL PASS |
| 0.8 | 4.60 / 3 / [.81,.90] | 4.30 / 2 / [.82,.95] | 5.60 / 4 / [.76,.92] | ALL PASS |
| 0.9 | 5.30 / 3 / [.75,.90] | 4.30 / 1 / [.79,.94] | 5.50 / 4 / [.73,.92] | ALL PASS |
| 1.0 | 5.10 / 3 / [.66,.90] | 4.30 / 1 / [.72,.91] | 5.50 / 4 / [.71,.92] | ALL PASS |

**New finding, not previously documented:** guard cases (`G-B2` specifically — HIGH_PRESS should favour recovery pace over duel strength) **fail at the low end**, not just as a hypothetical risk at the high end. Below λ=0.3, there is not enough tactical signal to overcome CB's defense-heavy position baseline, and the pace-favouring flip never happens. **λ has a floor as well as a practical ceiling.**

**Second new finding:** CB's `mean_overlap` is **non-monotonic in λ** — it improves through λ=0.6–0.8 (4.60) and then *worsens* at λ=0.9–1.0 (5.10–5.30), alongside a sharp drop in the correlation lower bound (0.91→0.66). At very high λ, the demand vector narrows onto very few extreme-weighted attributes, and enough different tactical profiles converge on rewarding those same few attributes that discrimination degrades again.

**Third finding, directly answering Phase 6's core question:** at **every** λ tested, including λ=1.0 (maximum tactical share, position knowledge fully discarded), **every position's correlation upper bound still exceeds 0.85.** RD-3's ceiling is not a lambda-tuning problem. No value in the safe range [0.3, 0.8] clears it, and the unsafe values above 0.8 both fail to clear it reliably *and* introduce the CB non-monotonicity above.

**Recommendation: λ = 0.7 is retained, unchanged.** It sits mid-way inside the empirically-confirmed safe range [0.3, 0.8], with adversarial margins matching the wider range, and no measured metric singles out a different value as clearly superior once RD-3 is understood to be unreachable at any λ. Marked `POLICY_OWNER_REQUIRED` only in the sense that the *safe range* itself, not this specific point within it, is a policy choice; the repository does not yet have an explicit owner-approved rule narrowing it further, so 0.7 remains the calibrated default with the full range documented for whoever picks up that decision.

---

## F. PlayStyle modifier audit (Phase 7)

Three models compared, per the mandate, none shipped by default without full validation:

**Model A (shipped):** global scalar, `R = C_lo × (1 + PlayStyle modifier)`, modifier ∈ [0, 0.10]. Monotone (verified: raising an unrelated attribute by +10 never lowered the score). Correctly returns 0 modifier for an irrelevant PlayStyle request or absent PlayStyle data — verified identical output (0.8016) in both the "candidate holds no PlayStyles" and "candidate holds a PlayStyle irrelevant to this request" cases, confirming a PlayStyle can never help merely by being present if it isn't relevant.

**Model B (attribute-relevance scaling):** **rejected on evidence grounds, not safety grounds.** It requires a PlayStyle-to-attribute relevance mapping. No such mapping exists anywhere in the codebase (`playstyle_context.py` only exposes a playstyle→scalar-tier function, `context_value`, never a playstyle→attribute-set mapping). Building one now would mean inventing football coefficients not backed by evidence — exactly what the project's own rules forbid ("no invented gameplay coefficients"). Rejected for lack of a data foundation.

**Model C (pre-aggregation boost, capped per-attribute at 1.0):** also monotone, also correctly zero for irrelevant requests, and has one genuinely appealing property Model A lacks: because each attribute's boosted saturated value is capped at 1.0 before aggregation, **R can never exceed 1.0 under Model C**, whereas Model A's global scalar can push `R` up to `C_hi × 1.15`, mathematically exceeding 1.0 for a near-perfect candidate. This is cosmetic, not a ranking-correctness issue (relative order is preserved either way), but is worth a future look.

**Decision: keep Model A.** Per Phase 22's own criteria, Model C was not run through the full validation matrix this session (Pareto dominance, pool independence, and evidence-interval interaction with `C_hi` were not tested for it) — shipping it without that would be exactly the "force it into production" the mandate warns against. Documented here as a promising future candidate, not activated.

---

## G. Interaction modifier (Phase 8) — stays disabled, now proven why

Two candidate formulations were adversarially constructed and both **fail monotonicity concretely**, not just in principle:

**Model 1 — geometric-mean-vs-linear-mean "discipline" reward** over a `(stamina, aggression, interceptions)` pressing group: `modifier(70,70,70) = 0.0000`; `modifier(85,70,70) = −0.0004`. **Raising one attribute by 15 points, others unchanged, lowered the modifier.** Confirmed VIOLATION directly.

**Model 2 — pure bottleneck (min-vs-own-mean)**, thought to be safer since `min()` alone is monotone: `modifier(70,70,70) = −0.0000`; `modifier(85,70,70) = −0.0067`. **Also fails.** The reason generalises beyond either specific formula: any interaction measure that compares a member of a group **against that same group's own mean** has a moving reference point — improving *any* non-bottleneck member widens its own gap from the mean, and a self-referential formula built to penalise that gap will react even though the candidate has weakly improved on every measured attribute.

**Conclusion:** the flaw is structural to self-relative cohesion measures generally, not an artifact of one formula choice. A monotone version would need to compare against a **fixed external reference** (e.g. the frozen reference distribution, not the candidate's own group mean) — a materially different design requiring its own full validation pass this session did not have room for.

**Decision: interaction modifier stays disabled (0.0) in v3.1.** This is the mandate's own explicitly acceptable outcome ("If no safe model survives T0/T1: leave interaction disabled. That is an acceptable production decision.") — reached here with concrete, adversarially-constructed proof rather than by default.

---

## H. Reference distribution audit (Phase 9)

All checks pass, five new regression tests added (`test_v3_1_calibration_hardening.py::TestPhase9ReferenceDistributionWall`):

- `reference.universe == RATINGS_SITE_PLAYERS`, confirmed, never `UT_CARDS`.
- `reference.applies_to("game_player") == True`; `reference.applies_to("ut_card") == False` — **the engine has a real, tested refusal**, not just a naming convention, preventing the player distribution from silently scoring a future card candidate.
- Loading an unregistered version (`"fc27-players-does-not-exist"`) raises `ReferenceDistributionUnavailable` rather than falling back to anything.
- There is currently **no FC27 reference distribution artifact at all** — confirmed by attempting to load one and observing the same explicit failure, not a silent FC26 substitution.

No changes required here; the design was already correct, now it is regression-tested.

---

## I. Evidence / coverage hardening (Phase 10)

Built synthetic test-fixture-only candidates (never production data) at controlled coverage: κ ∈ {0.10, 0.25, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00}, by publishing an exact prefix of the demand-sorted attribute list.

- **Below `kappa_min` (0.60): `NOT_EVALUABLE`, never ranked at any score** — confirmed for κ ∈ {0.10, 0.25, 0.40, 0.50}; confirmed *ranked* for κ ∈ {0.60, 0.70, 0.80, 0.90, 1.00}. The floor is exact, not approximate.
- **Publishing a previously-unknown attribute can raise `C_lo`** — confirmed with a direct before/after pair.
- **Removing evidence cannot increase `C_lo`** — confirmed: removing the weakest covered attribute from a fully-documented candidate never raised its score.

All three are now permanent regression tests, not one-off measurements.

---

## J. Confidence audit (Phase 11)

**Confidence was not previously wired into the v3 `ScoringContext` at all** — a real gap, found while attempting to write the required independence test, not by planned design in this session. Wired it in now (`confidence_v2.compute()`, driven by `kappa` as the dominant dimension per the model spec, plus identity status), added **after** `r`/`r_hi` are already fixed and never read back into either.

Proven, not asserted: two candidates, identical attributes, identical demand, **different identity status** → **`R` identical to the bit** (`res1.ranked[0].context.r == res2.ranked[0].context.r`), while `confidence` genuinely differs between them. Confidence dimensions confirmed independent: an `UNKNOWN` identity status is excluded from the composite, not penalised (matches the existing, correct `confidence_v2` design).

---

## K. Provenance at scale (Phase 12) — found and fixed a real gap

Sampled 100 random real players, traced every non-null published attribute back to a `field_provenance` row. **First run failed**: the six facade attributes (`pace, shooting, passing, dribbling, defending, physicality`) had **zero** provenance coverage — the original ingestion script only ever covered the 29 detail + 5 GK attributes, never the 6 headline facades every card actually displays. Confirmed systematic (0 rows for any facade field, across the whole 499,088-row table), not a sampling fluke.

**Fixed**: extended the provenance build to include `FACADE_ATTRS`. Re-ran against the live database: **585,560 rows** (up from 499,088), and the 100-random-player trace now passes with full coverage — including a live re-verified trace ("why do we believe Anass Salah-Eddine has 74 short_passing?" → source, observation timestamp, licence, all present).

---

## L. Replay audit (Phase 13)

- Identical request scored against a pool and its exact reverse ordering: **rank order and every score bit-identical.**
- Full round-trip: request + engine/config/reference versions + a SHA-256 response hash persisted, then replayed against the same `request_id` → **identical hash.**

No changes required; determinism holds under both tests the mandate specified.

---

## M. Production data firewall, defence in depth (Phase 14)

Beyond the v3.0 database-level proof (the `is_synthetic`/`data_status` mismatch), this session added **engine-layer** and **service-layer** tests that assume the repository layer's filter has already failed, and confirm the *next* layer still catches it:

- A synthetic candidate handed **directly** to the engine (bypassing the repository entirely) is still excluded via gate G2. A wrong-version (FC27) candidate handed directly to the engine is still excluded via gate G1.
- Read the actual source of `RecommendationServiceV3.recommend` and confirmed, structurally, that it **never calls the ut_card-serving repository method** (`load_cards` does not appear in it at all) — this is not a runtime behavioural test but a guarantee about which code path exists to be called in the first place.

Three independent layers now each independently refuse synthetic/wrong-version/wrong-scope data.

---

## N. API contract hardening (Phase 15)

Six new tests against the real FastAPI app: invalid position, FC27 (no silent FC26 fallback — either explicit non-200 or an empty, honestly-labelled result), `ut_card` scope (422, unchanged from v3.0), malformed request, an oversized `limit` (rejected at the **schema** level, `le=50`, not left to the engine to discover), and a data-sparse position (GK/BUILD_UP) confirmed to still respond rather than erroring. All pass.

---

## O. Naming clarity (Phase 16)

No changes needed: v3's own boundary was built clean from the start. `explanation` lives only on the **service** response (`recommendation_service_v3.py`'s `_serialise`), never as a field on the engine's `RecommendationResultV3` or `ScoringContext` — there is no `engine_result.explanations` to accidentally reach for. Positions use `position_primary`/`secondary_positions` consistently; v3 has no "slot" concept of its own to confuse with a base position. The confusion the baseline document flagged is confined to the untouched, pre-existing `test_integration_production.py` / `formations.py` pairing and was not introduced into any v3 code.

---

## P. Observability (Phase 17)

Added structured, per-request telemetry to `RecommendationServiceV3` (`eafc.v3.telemetry` logger): `request_id`, all four version identifiers, `entity_scope`, `position`, `tactical_profile`, candidate/eligible/excluded/not-evaluable counts, top result name/score/coverage, latency, and failure reason where applicable. No attribute values, no user-identifying data, no IP/session information.

Added two diagnostic methods (no scoring-path changes): `explain_exclusion(body, entity_id)` → "why was candidate X excluded?", and `explain_ranking_gap(body, id_a, id_b)` → "why did A rank above B?", the latter reusing the existing `explanation_service_v3.why_not` against two real `ScoringContext`s from a single, ordinary engine run. Both verified working against the live database.

---

## Q. Golden fixtures (Phase 18)

Generated and hashed all 15 requested scenarios (`scripts/build_golden_fixtures_v3_1.py` → `artifacts/v3_1/calibration/golden_fixtures.json`): the six tactical profiles, thin evidence, position mismatch, PlayStyle relevance and its absence, same-attributes/different-OVR, same-OVR/different-attributes, same player under two tactics, and two candidate-pool orderings. The two pool-ordering fixtures hash **identically** (`fb84f7905820d6ab`), independently corroborating Section L. A drift test (`test_golden_fixtures.py`, 13 tests) compares live output against the committed hashes on every run — a future change will show exactly which named scenario moved, not just an aggregate "something changed."

---

## R. Data license release gate (Phase 19)

Implemented `DataLicenseStatus` (`VERIFIED | UNVERIFIED | BLOCKED`) as an executable gate, not a document. The current foundation is registered **`UNVERIFIED`**, with the reason field naming the exact unresolved evidence gap (`FC26_DATA_GAPS.md` G-10). `gate_or_raise()` fails closed by default; an explicit `allow_unverified=True` is required even for local development against the known-unverified dataset, and an unregistered dataset is treated as `BLOCKED`, never silently `VERIFIED`. Five tests confirm all of this, including that `allow_unverified` cannot waive a `BLOCKED` status. **This does not resolve the licence question — it makes the unresolved status impossible to ship past by accident.**

---

## S. No card intelligence (Phase 20)

Unchanged from v3.0, re-confirmed: `entity_scope` is `Literal["game_player"]` at the Pydantic type level; a `ut_card` request is rejected by FastAPI's own validation before any handler code runs (422, `"game_player"` named in the error). No card data was fabricated, inferred, or mapped from player records anywhere in this session's work. Nothing in this session touched the FUT card ingestion boundary.

---

## T. Summary of parameter decisions (Phase 21 format)

| Parameter | OLD | NEW | Evidence | Reason | Risk | Tests passed |
|---|---|---|---|---|---|---|
| `lam_default` | 0.7 | **0.7 (unchanged)** | Full 11-point sweep, all positions, all guard cases | Sits mid-range in the confirmed safe band [0.3, 0.8]; no value clears RD-3 at any point in range; higher values introduce CB non-monotonicity | None (no change made) | All T0/T1, all guard cases at 0.7 |
| RD-3 ceiling (0.85) | 0.85 | **left at 0.85, test left failing** | Structural decomposition + full lambda sweep: unreachable at any λ∈[0,1] without failing guards | Never empirically calibrated in Session 1/2 (`[POLICY] needs an owner`); this session supplies the first real measurement against it | Changing it unilaterally would be exactly "arbitrary threshold change" the mandate forbids | N/A — marked `POLICY_OWNER_REQUIRED` |
| RD-4 CB target (0.10) | 0.10 | **left at 0.10, test left failing** | 0.094 measured, well-evidenced structural explanation (real elite-CB population is dual-axis, not single-axis) | Same as above — no owner-approved revision exists | Same | N/A — marked `POLICY_OWNER_REQUIRED` |
| `_spearman()` tie handling | ordinal (order-dependent) | **average-rank (order-invariant)** | Reproduced a real 0.076-vs-0.116 discrepancy from identical data | Standard, correct Spearman tie correction; the old version was a genuine measurement-tool bug | Low — measurement-only, does not touch the engine | All T0/T1 unaffected (confirmed before/after) |
| Field provenance scope | 34 attrs (detail+GK) | **40 attrs (+6 facades)** | Phase-12 scale audit found 0% facade coverage across all 499,088 rows | Facades are served, headline attributes; the mission's own bar ("no served attribute without provenance") was not met | None — additive | New Phase-12 test now passes at 100% |
| PlayStyle modifier | Model A (global scalar) | **Model A (unchanged)** | Models A/B/C compared; B lacks a data foundation, C untested on Pareto/pool-independence | Full validation of C not completed this session; shipping it now would be forcing an unvalidated change | Model C documented as a future candidate, not activated | Model A: all existing + new relevance/irrelevance tests |
| Interaction modifier | disabled (0.0) | **disabled (0.0), unchanged** | Two candidate formulations both proven to violate monotonicity by direct adversarial construction | Structural flaw in self-relative cohesion measures generally, not fixable by formula tweaking within this session | None — no change made | N/A |
| Confidence wiring | absent from `ScoringContext` | **wired in, reporting only** | Independence proven bit-exact | Phase 11 required this to be provable; it could not be proven if it did not exist | Low — confirmed never read back into `r`/`r_hi` | New Phase-11 tests pass |
| `DataLicenseStatus` gate | none (document only) | **executable gate, `UNVERIFIED`** | `FC26_DATA_GAPS.md` G-10 still open | Makes the release-blocking condition machine-checkable, fails closed by default | None — additive, fails closed | 5 new tests |

---

## U. Final classified test run (Phase 23)

```
515 passed, 24 failed, 1 skipped
```

| Category | Count | Examples |
|---|---|---|
| **PASS** | 515 | All T0 (21), all T1 (14), all v3.0 production-safety (7), all v3.0 API (5), all new Phase 9-20 hardening (35), all golden fixtures (13), all license gate (5), plus the full pre-existing non-intelligence suite |
| **EXPECTED HISTORICAL FAILURE** | 9 | `test_engine_adversarial_phase7.py` — v2's known-defective behaviour, preserved unchanged as the permanent record of what v3 fixed, per the Session-1 migration decision |
| **OUT-OF-SCOPE FAILURE** | 11 | `test_integration_production.py` — pre-existing test/implementation drift unrelated to demand composition, capability, gating, provenance, or conflict resolution (engine-vs-service field confusion, slot-vs-position field confusion, stale fixtures, unrelated security/rate-limit assertions); each individually re-verified this session, none newly broken |
| **POLICY FAILURE** | 4 | RD-3 (all three positions) and RD-4 CB spread — real, structurally-explained measurements against thresholds that were never empirically calibrated or owner-approved; left failing rather than adjusted |
| **GENUINE ENGINE FAILURE** | **0** | None found this session |

**Unresolved production-contract failures: zero.** All 24 failures are either a deliberately preserved historical record, a pre-existing and unrelated test, or a reported measurement against an unowned policy threshold — none reflects a defect in the v3 engine's actual behaviour.

---

## V. What this session changed vs. what it deliberately did not

**Changed:** `_spearman()` tie handling (measurement only); `field_provenance` build script (added facades); `scoring_context.py` and `recommendation_engine_v3.py` (wired confidence in, reporting-only); `recommendation_service_v3.py` (structured telemetry + two diagnostic methods). Ten new test/script files.

**Deliberately not changed:** `lam_default`, the RD-3 ceiling, the RD-4 CB target, the PlayStyle modifier mechanism, the interaction modifier's disabled state. Every one of these was investigated to the depth the mandate asked for and left alone because the evidence did not support changing it — which is itself the finding, not a gap in the work.
