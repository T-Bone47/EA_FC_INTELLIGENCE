# FC27 intelligence engine V3.2.1

## Results

V3.2.1 improves how explicit preferences affect tactical recommendations and reports how much the published evidence separates two candidates. Default scoring continues to use the frozen V3.2 configuration `v3.2-2026-09-30-r1`.

- The Studio sends a weight of 2 for the selected attribute and displays the submitted preference. In the FC27 high-press striker test, choosing finishing increased its share of demand from 4.53% to 9.07%.
- Preference adjustments preserve nonnegative demand. The previously negative minimum demand weight in the tested low-weight scenario was −2.93% and is now +1.32% after zero-weight dimensions are dropped and the remainder is normalized. Hiding a scoring attribute can no longer improve the lower-bound score through a negative weight.
- PlayStyle names match consistently across case, spacing and a trailing plus marker. The bonus respects contextual affinity and tier. In the controlled striker test, Quick Step at the requested tier earned 0.075 and Far Reach earned 0.035. A base-tier Quick Step received 60% of Quick Step+'s contextual credit when plus was preferred.
- Recommendations, comparison and what-if responses report the modelled lead range. Recommendations distinguish near ties, leads sensitive to missing attributes and leads that remain separated across the modelled range. The range represents missing attribute evidence and uses the existing tie tolerance.
- The recommendation service checks the deployment at request time. Card availability and card serving evaluate the same request and settings with the existing loopback and environment restrictions.

## Research data evaluated

| Input | Release or purpose | Observations |
| --- | --- | ---: |
| FC27 players | `fc27-players-2026-09-r1` | 19,789 |
| FC27 cards | `fc27-card-items-local-r1` | 9,962 |
| October supplemental source | Staged comparison across matching item IDs and OVRs | 10,762 |

The two serving releases use separate references. The player release includes 17,849 men's and 1,940 women's records. The October source supplied 240,349 comparable numeric attribute pairs, of which 234,864 agreed. All 5,485 discrepancies were in the aggregate dribbling rating. The distinct detailed dribbling field agreed in all 6,867 comparable pairs. The supplemental observations were used for a reproducible field audit and retained in staging.

The comparison ran 144 default scenarios across 12 positions, four tactical profiles, both player divisions and the separate card scope. The ordered top 10 IDs, scores, upper bounds, coverage and candidate counts were identical to the V3.2 baseline in every scenario. Changing tactical profile affected the results in all 35 scorable position and scope combinations. Four card goalkeeper scenarios remained unscored because the card release lacks an adequate goalkeeper reference.

The database held zero accepted, shared owner, user or controlled gameplay observations for the card snapshot. The evidence measures scoring behavior and input agreement. Empirical gameplay calibration awaits accepted, comparable match observations.

## Reproduction

Run the benchmark from the project root with the existing PostgreSQL research release and a local application configuration.

```text
python -m verification.evaluate_fc27_engine results/engine.json --supplement-output results/supplement.json
```

`BEFORE.json` and `AFTER.json` retain a per-scenario SHA-256 fingerprint of the ordered top 10 candidate IDs, scores, upper bounds and coverage. Individual candidate rows are outside the evidence package. `SUPPLEMENT.json` reports per-field counts.

Run the backend regression suite against a disposable database with the same pinned releases and existing migrations.

```text
python -m pytest backend/tests/test_v3_expert_preferences.py backend/tests/test_engine_v3_adversarial.py backend/tests/test_engine_v3_invariants.py backend/tests/test_v3_2_missing_data.py backend/tests/test_golden_fixtures_v3_2.py backend/tests/test_v3_2_config.py backend/tests/test_recommendations_v3_api.py backend/tests/test_v3_api_contract.py backend/tests/test_v3_response_blocks.py backend/tests/test_v3_production_safety.py backend/tests/test_zero_budget_research.py backend/tests/test_fc27_availability.py backend/tests/test_phase30_card_lab.py backend/tests/test_phase31_performance.py -q
```

The focused PostgreSQL-backed backend suite passed all 146 tests. All 95 frontend tests passed across the unit and live-API runs. The three live tests verify the FC26 ladder, pairwise explanations and what-if against the running backend. The React production build passed. The focused Chrome journey used real local and production-mode FastAPI processes and the existing PostgreSQL research database. It verified FC27 opt-in, player search and detail, a personalized high-press request, player and exact-version card comparison, real squad optimization, mobile rendering, research revocation and production refusals. See `BROWSER.json`.

Set `E2E_API_URL`, `E2E_PRODUCTION_URL`, `AVAILABILITY_RESULTS_DIR` and optionally `CHROME_PATH`, then run `node frontend/verification/fc27-availability.mjs`. Use a production-mode test server bound to loopback for the production endpoint. The frontend and database evidence is local research only.
