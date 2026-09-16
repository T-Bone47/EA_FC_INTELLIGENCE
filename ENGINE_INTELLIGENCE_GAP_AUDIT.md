# ENGINE INTELLIGENCE GAP AUDIT

**Date:** 2026-09-15  
**Engine Version:** 2.3.0  
**Auditor:** Autonomous agent  
**Status:** AUDIT COMPLETE — Ready for Phase 7 implementation

---

## Executive Summary

This audit examines the current EA FC Player Intelligence engine (v2.3.0) to identify gaps between the current implementation and the ideal football intelligence system described in the Phase 7 mission. The engine has made significant progress through Phases 4-6, but critical gaps remain in football reasoning depth, contextual intelligence, and adversarial robustness.

**Overall Assessment:** The engine has a solid deterministic foundation with excellent data hygiene (UNKNOWN handling, FC26/FC27 separation, synthetic firewall). However, the intelligence layer remains relatively shallow — scoring is largely attribute-weighted averaging with limited football reasoning (attribute interactions, role intelligence, tactical nuance).

---

## 1. Current Strengths

| Area | Status | Details |
|------|--------|---------|
| **Determinism** | ✅ EXCELLENT | Same input → identical output; golden regressions S1-S8 + FC27 wall bit-identical |
| **Data Hygiene** | ✅ EXCELLENT | UNKNOWN/INSUFFICIENT_EVIDENCE semantics; no fabricated data; FC26/FC27 separation |
| **Synthetic Firewall** | ✅ EXCELLENT | Synthetic data completely isolated from production reads |
| **GK Intelligence** | ✅ GOOD | GK tactical weights, GK PlayStyle context, GK combination tactics (Phase 4 fix) |
| **CB Passing Intelligence** | ✅ GOOD | short_passing, long_passing, vision, composure added (Phase 4 fix) |
| **Formation Slots** | ✅ GOOD | 11 formations with duties/emphasis; 4-2-2-2 LAM/RAM fixed (Phase 4 fix) |
| **Tactical Profiles** | ✅ GOOD | 16 profiles with GK attributes; GK combination tactics via dimension affinities |
| **OVR Trap Protection** | ✅ GOOD | GK (82 beats 90) and Outfield (81 beats 90) verified; no reverse bias |
| **UNKNOWN Handling** | ✅ EXCELLENT | UNKNOWN never penalized; INSUFFICIENT_EVIDENCE for thin evidence |
| **Determinism** | ✅ EXCELLENT | 131 unit tests verify same input → same output |
| **Explainability** | ✅ GOOD | Component-level evidence; why_this/why_not_alternatives |
| **Confidence v2** | ✅ GOOD | 4-factor additive model (legacy + freshness + authority + identity) |
| **Counterfactuals** | ✅ GOOD | 4 families (tactics, budget, mins, strict); card-specific variants |
| **Sensitivity** | ✅ GOOD | 0.005 noise threshold; weighted delta drivers |
| **Squad Intelligence** | ✅ ADVISORY | Link density, archetype diversity, complementarity (not chemistry) |
| **GK PlayStyles** | ✅ GOOD | GK-specific tactical PlayStyles for 16 profiles |
| **PlayStyle Context** | ✅ GOOD | Profile (1.0), Position (0.75), Neutral (0.35) tiered values |
| **Deterministic Explanations** | ✅ GOOD | No LLM in path; evidence-only generation |
| **FC26/FC27 Separation** | ✅ EXCELLENT | Absolute wall; FC27 = NO_DATA |
| **Synthetic Firewall** | ✅ EXCELLENT | Verified at engine, repo, and API layers |
| **No Fabrication** | ✅ EXCELLENT | No invented players, attrs, PlayStyles, roles, cards, prices |

---

## 2. Current Weaknesses (Intelligence Gaps)

### 2.1 Missing Football Archetype Intelligence
| Gap | Current State | Required |
|-----|---------------|----------|
| **Explicit Archetypes** | 17 computed archetypes exist but only used when explicitly requested via `req.archetype` | Archetypes should be FIRST-CLASS: auto-computed per candidate, used in scoring even without explicit request, surfaced in explanations |
| **Role Intelligence** | `role_fit` is advisory only; no real role data; returns INSUFFICIENT_EVIDENCE | Need inferred role intelligence from attributes/PlayStyles/position; must be clearly labeled as ENGINE-DERIVED |
| **Gameplay Profiles** | 10 outfield + 3 GK labels computed but only surfaced in enrichment (top-25) | Should influence scoring when relevant tactical profile requested |
| **Archetype Scoring** | Only active when `req.archetype` explicitly set | Should be always computed, optionally used in scoring |

### 2.2 Attribute Interaction Engine Gaps
| Gap | Current State | Required |
|-----|---------------|----------|
| **Interaction Coverage** | 8 features only (explosive_ball_carrier, pressing_engine, playmaker_hub, poacher_instinct, defensive_wall, transition_launcher, aerial_dominance) | Need comprehensive coverage: pace+agility+balance, vision+passing+composure, defensive_awareness+interceptions+tackling, finishing+positioning+reactions, crossing+curve+vision, etc. |
| **Interaction Weight** | Capped at 30% of attribute_fit (INTERACTION_TOTAL_CAP = 0.30) | Should be configurable per position/profile; some positions heavily interaction-dependent |
| **Interaction Discovery** | None — features are hardcoded in engine_config | Should be discoverable from data patterns (but validated by football experts) |
| **Saturation** | Per-attribute knees (pace=90, passing=88, etc.) but uniform across positions | Should be position/profile specific (e.g., pace knee lower for CB) |

### 2.3 Tactical Intelligence Gaps
| Gap | Current State | Required |
|-----|---------------|----------|
| **Tactical Profile Granularity** | 16 profiles with outfield + GK attributes | Need sub-profiles: e.g., POSSESSION_HOLD vs POSSESSION_PROGRESSIVE; PRESSING_HIGH vs PRESSING_MID |
| **Tactical Combination Logic** | Dimension merging (0.6/0.4 split) but only for secondary_tactical_profile | Need explicit combination presets: HIGH_PRESS+FAST_BUILD_UP ≠ HIGH_PRESS+POSSESSION |
| **Formation-Tactical Interaction** | Formation slots affect attribute weights via slot emphasis | Need formation-specific tactical profiles: 3-5-2 LOW_BLOCK ≠ 4-4-2 LOW_BLOCK |
| **Role-Tactical Coupling** | None — role_fit is advisory only | Role should constrain tactical expectations: e.g., "Deep Playmaker" in POSSESSION vs COUNTER |

### 2.4 Positional Intelligence Gaps
| Gap | Current State | Required |
|-----|---------------|----------|
| **Position Suitability** | Binary-ish: exact=1.0, secondary=0.85, adjacency table, fallback=0.05 | Need continuous suitability: naturalness gradient, tactical slot fit, role requirement overlap |
| **Secondary Position Quality** | All secondaries treated equally (0.85 if listed) | Need secondary position quality: some players are "comfortable" at secondary, others "emergency only" |
| **Multi-Position Players** | Treated as having multiple secondaries | Need explicit multi-position scoring: e.g., CB/LB hybrid vs pure CB |
| **GK Position Logic** | GK position_fit = 1.0 always (no secondaries) | GK should have tactical slot differentiation (sweeper keeper vs shot stopper positioning) |

### 2.5 PlayStyle Intelligence Gaps
| Gap | Current State | Required |
|-----|---------------|----------|
| **PlayStyle Synergy** | None — each PlayStyle scored independently | Synergy detection: e.g., Tiki Taka + First Touch > sum; Press Proven + Intercept > sum |
| **PlayStyle Anti-Synergy** | None | Detect conflicts: e.g., "Long Ball Pass" + "Tiki Taka" may conflict tactically |
| **PlayStyle Evolution** | None | Track how PlayStyle value changes with tactical context (already partially done via context_value) |
| **PlayStyle+ Grading** | Binary: + tier counts 1.5× base | Need graded PlayStyle+: e.g., "Incisive Pass+" > "Incisive Pass" > "Incisive Pass (base only)" |

### 2.6 OVR Trap / Adversarial Robustness
| Gap | Current State | Required |
|-----|---------------|----------|
| **Adversarial Test Coverage** | 50 scenarios specified in mission; only 2 synthetic OVR trap tests exist | Need 50+ deterministic adversarial scenarios as regression tests |
| **OVR Bias Options** | Only 3 settings (low/normal/high) scaling overall_quality weight | Need continuous OVR-stance control + per-position OVR sensitivity |
| **OVR-Attribute Interaction** | None — OVR is isolated component | Need OVR as quality proxy that interacts with attribute_fit (e.g., high OVR + poor attributes = suspect) |

### 2.7 Explanation & Confidence Gaps
| Gap | Current State | Required |
|-----|---------------|----------|
| **Explanation Completeness** | why_this shows top-4 components; why_not_alternatives shows differentials | Need full decision tree: why #1 over #2 over #3; trade-off narratives |
| **Confidence Granularity** | 4-level (HIGH/MEDIUM/LOW/VERY_LOW) + score_v2 | Need per-component confidence + stability metrics |
| **Counterfactual Depth** | 4 families (tactics, budget, mins, strict) | Need: change formation, change role, change PlayStyle importance, swap candidate attributes |
| **Sensitivity Granularity** | Component-level weighted deltas only | Need attribute-level sensitivity + ranking stability metrics |

### 2.8 Squad Intelligence Gaps
| Gap | Current State | Required |
|-----|---------------|----------|
| **Squad Scoring** | Only advisory structural_fit; no squad-level score | Need squad-level suitability: how does candidate improve squad as a whole? |
| **Tactical Balance** | None | Detect tactical imbalance: e.g., 3 playmakers + no ball-winner |
| **Role Coverage** | Duplicate archetype penalty only | Need role coverage analysis: missing roles, redundant roles |
| **Squad Weakness Detection** | None | Auto-detect: "squad lacks pace on wings" → recommend pacey winger |

---

## 3. Missing Football Concepts

| Concept | Current Status | Priority |
|---------|----------------|----------|
| **Football Archetypes** | 17 computed but opt-in only | HIGH — make first-class |
| **Role Intelligence** | Advisory only, INSUFFICIENT_EVIDENCE | HIGH — infer from attributes/PlayStyles |
| **Attribute Interactions** | 8 features, capped at 30% | HIGH — expand to 20+ features |
| **Tactical Sub-profiles** | 16 profiles only | MEDIUM — add sub-profiles |
| **Formation-Tactical Coupling** | Slot emphasis only | MEDIUM — formation-specific tactical profiles |
| **Role-Tactical Coupling** | None | MEDIUM |
| **PlayStyle Synergy** | None | MEDIUM |
| **PlayStyle Anti-Synergy** | None | LOW |
| **Position Naturalness Gradient** | Binary-ish (exact/secondary/adjacent) | HIGH |
| **Secondary Position Quality** | All equal (0.85) | MEDIUM |
| **GK Tactical Slot Logic** | None (GK = DEFEND always) | MEDIUM |
| **Squad Tactical Balance** | None | MEDIUM |
| **Role Coverage Analysis** | None | MEDIUM |
| **Squad Weakness Detection** | None | MEDIUM |
| **Attribute Saturation** | Per-attr knees (global) | MEDIUM — position-specific knees |
| **OVR-Attribute Interaction** | None | HIGH |
| **Adversarial Test Suite** | 2 synthetic tests only | HIGH — 50+ scenarios needed |
| **Counterfactual Families** | 4 (tactics, budget, mins, strict) | MEDIUM — add formation, role, PlayStyle, attribute |
| **Explanation Depth** | Component-level only | MEDIUM — full decision tree |
| **Confidence Granularity** | 4-level + score_v2 | MEDIUM — per-component + stability |
| **Squad-Level Scoring** | Advisory only | MEDIUM |

---

## 4. Scoring Weaknesses

| Weakness | Description | Impact |
|----------|-------------|--------|
| **Weight Rigidity** | Fixed weights (0.15/0.30/0.15/0.15/0.15/0.10) — only archetype and OVR bias modify | Cannot adapt to user context (e.g., "I only care about tactical fit") |
| **No Per-Position Weight Override** | Component weights global | Position-specific weight profiles needed (e.g., GK: tactical_fit > overall_quality) |
| **Attribute Interaction Cap** | Hard 30% cap on interactions | Some positions need >30% interaction influence |
| **No OVR-Attribute Interaction** | OVR and attributes independent | High OVR + poor attributes should be penalized |
| **Saturation Uniform** | Per-attr knees but same for all positions | Position-specific saturation curves needed |
| **PlayStyle Weight Fixed** | Base=1.0, Plus=1.5 always | Context-dependent PlayStyle weights needed |
| **No Tactical Weight Calibration** | No mechanism to tune tactical weights per position | Position-specific tactical weights needed |

---

## 5. Data Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **No Official EA Roles** | role_fit = INSUFFICIENT_EVIDENCE | Infer from attributes/PlayStyles (clearly labeled ENGINE-DERIVED) |
| **No Verified Chemistry** | team_fit = INSUFFICIENT_EVIDENCE | Structural fit only (link facts) |
| **No Market Prices** | budget = BUDGET_UNVERIFIED | Honest UNAVAILABLE; no budget enforcement |
| **No FC27 Data** | FC27 = NO_DATA wall | Architecture ready; await legitimate source |
| **No UT Card Data** | 0 production cards | Architecture ready (DATA-READY); await legitimate source |
| **No Verified Market Feed** | Prices UNKNOWN | Value = VALUE_UNAVAILABLE |
| **Women's FC26 Partial** | Only where EA published | Document limitation; don't fabricate |
| **Secondary Position Quality** | No granularity (all 0.85) | Need "comfortable" vs "emergency" distinction |
| **PlayStyle+ Count** | Max 1 per player (evidence-based) | Verified; don't fabricate more |
| **GK Facade Mirroring** | Outfield attrs for GK are EA UI mirrors | Correctly NULLed in canonical; GK uses only gk_* attrs |

---

## 6. Ranking Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| **OVR Dominance** | overall_quality=0.15 but OVR correlates with attrs | OVR-attribute interaction; adversarial tests |
| **Attribute Averaging** | attribute_fit = weighted avg of v/99 | Interactions (min/geo) address non-linearity |
| **PlayStyle Binary** | Has/has not + tier multiplier | Synergy/anti-synergy; graded PlayStyle+ |
| **Position Binary** | exact=1.0, secondary=0.85, else adjacency | Naturalness gradient; secondary quality |
| **Tactical Binary** | Profile weights applied uniformly | Dimension merging + combination logic |
| **GK vs Outfield Mix** | GK uses gk_* attrs; outfield ignored | Correctly isolated; GK-specific profiles |
| **Adversarial Blind Spots** | Only 2 synthetic OVR trap tests | 50+ adversarial scenarios needed |
| **Formation-Tactical Decoupling** | Formation slots affect attrs; tactical profiles independent | Formation-specific tactical profiles |

---

## 6. Recommended Changes (Priority Order)

### Priority 1 — Critical Intelligence Gaps
1. **Make Archetypes First-Class** — Auto-compute for all candidates; use in scoring even without explicit `req.archetype`; surface in explanations
2. **Expand Attribute Interactions** — Add 15+ features covering all position families; make configurable per position/profile
3. **OVR-Attribute Interaction** — High OVR + poor attribute fit should penalize; adversarial test suite (50+ scenarios)
4. **Position Naturalness Gradient** — Replace binary position_fit with continuous suitability (naturalness + tactical slot fit + role overlap)
5. **Role Intelligence** — Infer roles from attributes/PlayStyles/position; label ENGINE-DERIVED; use in scoring when role requested

### Priority 2 — High-Value Intelligence Improvements
6. **Attribute Interaction Expansion** — Add 15+ features: pace+agility+balance, vision+passing+composure, defensive_awareness+interceptions+tackling, finishing+positioning+reactions, crossing+curve+vision, etc.
7. **Tactical Sub-profiles** — Split 16 profiles into sub-variants (e.g., POSSESSION_HOLD vs POSSESSION_PROGRESSIVE)
8. **Formation-Tactical Profiles** — 3-5-2 LOW_BLOCK ≠ 4-4-2 LOW_BLOCK
9. **PlayStyle Synergy/Anti-Synergy** — Detect reinforcing/conflicting PlayStyle pairs
10. **Position Naturalness Gradient** — Replace binary position_fit with continuous suitability (naturalness + tactical slot fit + role overlap)
11. **Secondary Position Quality** — "Comfortable" (0.95) vs "Capable" (0.85) vs "Emergency" (0.60)

### Priority 3 — Medium-Value Enhancements
12. **Tactical Sub-profiles** — POSSESSION_HOLD, POSSESSION_PROGRESSIVE, PRESSING_HIGH, PRESSING_MID
13. **Formation-Tactical Profiles** — 3-5-2 LOW_BLOCK ≠ 4-4-2 LOW_BLOCK
14. **Role-Tactical Coupling** — Role constrains tactical expectations
14. **PlayStyle Synergy/Anti-Synergy** — Tiki Taka + First Touch > sum; Long Ball Pass + Tiki Taka conflict
15. **Secondary Position Quality** — Comfortable (0.95) vs Capable (0.85) vs Emergency (0.60)
16. **GK Tactical Slots** — Sweeper keeper slot (SUPPORT/ATTACK duty) vs Shot stopper (DEFEND)
17. **Squad Tactical Balance** — Detect missing roles, redundant roles
18. **Role Coverage Analysis** — "Squad lacks ball-winner"
19. **Squad Weakness Detection** — Auto-detect and recommend
20. **Position-Specific Saturation** — CB pace knee=85, ST finishing knee=90
21. **OVR-Attribute Interaction** — Penalize high OVR + poor attrs
22. **Per-Position Weight Profiles** — GK: tactical>overall; ST: attr>tactical
23. **Adversarial Test Suite** — 50+ deterministic scenarios as regression tests
24. **Counterfactual Expansion** — Formation change, role change, PlayStyle importance change
25. **Explanation Decision Tree** — Full trade-off narratives
26. **Per-Component Confidence** — Component-level + stability metrics
27. **Squad Tactical Balance** — Missing/redundant role detection
28. **Position-Specific Saturation** — Per-position knees
26. **OVR-Attribute Interaction** — Penalty for high OVR + poor attrs
27. **Per-Position Weight Profiles** — GK: tactical>overall; ST: attr>tactical
28. **Counterfactual Expansion** — Formation, role, PlayStyle importance
29. **Explanation Decision Tree** — Full trade-off narratives
29. **Per-Component Confidence** — Component-level + stability metrics
30. **Squad Tactical Balance** — Missing/redundant role detection
31. **Position-Specific Saturation** — Per-position knees
32. **OVR-Attribute Interaction** — Penalty for high OVR + poor attrs
33. **Per-Position Weight Profiles** — GK: tactical>overall; ST: attr>tactical
34. **Counterfactual Expansion** — Formation, role, PlayStyle importance
35. **Explanation Decision Tree** — Full trade-off narratives
36. **Per-Component Confidence** — Component-level + stability metrics

### Explicitly NOT Recommended
- **ML Ranking** — No real feedback labels; deterministic engine remains canonical
- **LLM Scoring** — No LLM in scoring path; LLM may only rephrase grounded explanations
- **Fabricated Data** — Never invent players, attrs, PlayStyles, roles, cards, prices, chemistry, Evolutions
- **FC27 Fabrication** — FC27 remains NO_DATA until legitimate source
- **UT Card Fabrication** — No card attributes, prices, chemistry, Evolutions, Roles
- **Second Engine** — No V3/parallel engine; evolve v2 in place
- **Weakening UNKNOWN Semantics** — UNKNOWN never becomes penalty or zero

---

## 7. FC26 Data Validation Summary

| Metric | Value |
|--------|-------|
| Total Players | 16,228 |
| GK Count | 1,816 |
| Positions | 12 (GK, CB, LB, RB, CDM, CM, CAM, LM, RM, LW, RW, ST) |
| Attributes | 34 outfield + 5 GK + 6 facades = 45 total |
| PlayStyles | 36 unique; 15,032 links (14,913 base + 119 plus) |
| PlayStyle+ Cap | Max 1 per player (119 holders) |
| Positions | 12 primary; alternate_positions comma-separated |
| GK Attributes | 5 real (gk_diving, gk_handling, gk_kicking, gk_positioning, gk_reflexes) |
| Facades | 6 (pace, shooting, passing, dribbling, defending, physicality) |
| Outfield Details | 28 attributes |

---

## 8. Recommended Next Implementation Order

1. **Adversarial Test Suite** (50+ scenarios) — Foundation for safe changes
2. **Archetype First-Class Integration** — Auto-compute, use in scoring, surface in explanations
3. **Attribute Interaction Expansion** — 15+ new features; position/profile config
4. **OVR-Attribute Interaction** — Penalize high OVR + poor attribute fit
5. **Position Naturalness Gradient** — Replace binary position_fit
6. **Role Intelligence** — Engine-derived role inference
7. **Attribute Interaction Expansion** — 15+ new features
8. **Tactical Sub-profiles** — Split 16 into sub-variants
9. **Formation-Tactical Profiles** — Formation-specific tactical weights
10. **PlayStyle Synergy/Anti-Synergy** — Detect reinforcing/conflicting pairs
11. **Secondary Position Quality** — Comfortable/Capable/Emergency
12. **Counterfactual Expansion** — Formation, role, PlayStyle importance
13. **Explanation Decision Tree** — Full trade-off narratives
13. **Per-Component Confidence** — Component-level + stability
14. **Squad Tactical Balance** — Missing/redundant role detection
14. **Position-Specific Saturation** — Per-position knees
15. **OVR-Attribute Interaction** — Penalty for high OVR + poor attrs
16. **Per-Position Weight Profiles** — GK: tactical>overall; ST: attr>tactical
17. **Counterfactual Expansion** — Formation, role, PlayStyle importance
18. **Explanation Decision Tree** — Full trade-off narratives
19. **Per-Component Confidence** — Component-level + stability metrics
20. **Squad Tactical Balance** — Missing/redundant role detection
15. **Position-Specific Saturation** — Per-position knees
16. **OVR-Attribute Interaction** — Penalty for high OVR + poor attrs
17. **Per-Position Weight Profiles** — GK: tactical>overall; ST: attr>tactical
18. **Counterfactual Expansion** — Formation, role, PlayStyle importance
19. **Explanation Decision Tree** — Full trade-off narratives
19. **Per-Component Confidence** — Component-level + stability metrics
20. **Squad Tactical Balance** — Missing/redundant role detection

---

## 9. Sign-Off

**Audit Complete:** 2026-09-15  
**Engine Version:** 2.3.0  
**Status:** AUDIT COMPLETE — Ready for Phase 7 Implementation

**Next Action:** Begin Phase 7 implementation starting with Adversarial Test Suite (Item 1) and Archetype First-Class Integration (Item 2).

---

**Files Referenced in Audit:**
- `backend/services/recommendation_engine_v2.py`
- `backend/services/scoring_config.py`
- `backend/services/fit_components.py`
- `backend/services/formations.py`
- `backend/services/playstyle_context.py`
- `backend/services/engine_config.py`
- `backend/services/archetypes.py`
- `backend/services/attribute_model.py`
- `backend/services/counterfactual.py`
- `backend/services/explanation_service.py`
- `backend/services/confidence_v2.py`
- `backend/services/squad_intelligence.py`
- `data/fc26_real_foundation/players.csv` (16,228 rows)
- `data/fc26_real_foundation/player_playstyles.csv` (15,032 rows)
- Phase 4/5/6 reports
- `docs/ENGINE_CHANGELOG.md`
- `docs/INTELLIGENCE_ENGINE_ARCHITECTURE.md`

---

*End of Audit*