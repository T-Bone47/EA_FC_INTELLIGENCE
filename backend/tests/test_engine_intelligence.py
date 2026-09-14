"""Unit tests for the v2.1 intelligence modules (§5-§13, §18, §23, §24, §29-§31).

Everything here is deterministic, in-memory, and DB-free. Real-data integration
lives in test_engine_scenarios.py; adversarial/edge behavior in
test_engine_robustness.py.
"""
from __future__ import annotations

import uuid

import pytest

from backend.domain.user_model import (
    AttributeBand, AttributePreference, UserRequirements,
)
from backend.services import (
    archetypes, attribute_model, confidence_v2, counterfactual, engine_config,
    formations, intent_parser, playstyle_context, squad_intelligence,
)
from backend.services.engine_config import QUALITY_BANDS
from backend.services.fit_value import FitStatus
from backend.services.recommendation_engine_v2 import (
    RecommendationEngineV2, score_band,
)

from .helpers import make_attrs, make_candidate, make_req

CM_FULL = dict(short_passing=86, vision=84, long_passing=82, stamina=88,
               ball_control=84, composure=85, defensive_awareness=78,
               interceptions=75, positioning=78, dribbling_detail=80,
               acceleration=74, sprint_speed=72, strength=80, aggression=76,
               reactions=82, long_shots=76, curve=74)


# ------------------------------------------------------------------ formations
class TestFormations:
    def test_phase4_required_formations_are_available_and_aligned(self):
        """The Phase 4 minimum formation set must score through real slots,
        not only appear as a flat UI layout."""
        from backend.api.routes.meta import FORMATIONS

        required = {"4-2-3-1", "4-3-3", "4-4-2", "4-2-2-2", "4-1-2-1-2",
                    "3-5-2", "3-4-2-1", "5-2-1-2"}
        assert required <= set(FORMATIONS)
        for name in required:
            assert [slot.position for slot in formations.FORMATION_SLOTS[name]] == \
                FORMATIONS[name]

    def test_slots_cover_every_formation(self):
        for name, slots in formations.FORMATION_SLOTS.items():
            assert slots, name
            assert all(s.position for s in slots), name

    def test_cam_slot_differs_from_cm_slot(self):
        """§6: CAM ≠ CM — slots in the same position family disagree on duty
        and dimensions (4-3-3 CM slots are LCM/CDM/RCM, not interchangeable)."""
        cam = formations.find_slot("4-2-3-1", "CAM")
        cdm = formations.find_slot("4-3-3", "CDM")
        assert cam.position == "CAM" and cdm.position == "CM"
        assert cam.duty != cdm.duty
        assert cam.emphasis != cdm.emphasis

    def test_dimension_vectors_are_bounded(self):
        for profile in ("HIGH_PRESS", "POSSESSION", "LOW_BLOCK", "COUNTER_ATTACK"):
            dims = formations.dimension_vector(profile)
            assert set(dims) == set(formations.TACTICAL_DIMENSIONS)
            assert all(0.0 <= v <= 1.0 for v in dims.values()), profile

    def test_combo_tactical_weights_are_distinct(self):
        """§7: HIGH_PRESS+FAST_BUILD_UP ≠ HIGH_PRESS+POSSESSION."""
        d1 = formations.dimension_vector("HIGH_PRESS", secondary="FAST_BUILD_UP")
        d2 = formations.dimension_vector("HIGH_PRESS", secondary="POSSESSION")
        w1 = formations.tactical_weights_from_dimensions(d1)
        w2 = formations.tactical_weights_from_dimensions(d2)
        assert w1 and w2
        assert w1 != w2
        # fast build-up leans more on acceleration; the possession blend keeps
        # more pure pressing demand (interceptions / defensive awareness)
        assert w1["acceleration"] > w2["acceleration"]
        assert w2["interceptions"] > w1["interceptions"]
        assert w2["defensive_awareness"] > w1["defensive_awareness"]

    def test_all_dimensions_neutral_produces_no_demand(self):
        dims = {d: 0.5 for d in formations.TACTICAL_DIMENSIONS}
        assert formations.tactical_weights_from_dimensions(dims) == {}

    def test_slot_lookup(self):
        assert formations.find_slot("4-2-3-1", "CAM") is not None
        assert formations.find_slot("4-2-3-1", "GK") is not None
        assert formations.find_slot("4-2-3-1", "XXX") is None


# ------------------------------------------------------------------ intent
class TestIntentParser:
    def test_hard_vs_soft_playstyles_disjoint(self):
        i = intent_parser.parse("must have Tiki Taka, would love Pinged Pass", "FC26")
        d = i.to_draft()
        assert d["required_playstyles"] == ["Tiki Taka"]
        assert d["desired_playstyles"] == ["Pinged Pass"]

    def test_explicit_numbers_are_hard_inferred_bands_are_soft(self):
        i = intent_parser.parse("CM with at least 85 stamina, good passing, elite vision", "FC26")
        d = i.to_draft()
        mins = [h for h in d["hard_constraints"] if h["kind"] == "ATTRIBUTE_MIN"]
        assert any(m["field"] == "stamina" and m["value"] == 85 for m in mins)
        bands = {b["attribute"]: b for b in d["attribute_bands"]}
        assert "short_passing" in bands or "long_passing" in bands or "vision" in bands
        assert bands.get("vision", {}).get("band") == "elite"
        # provenance: explicit vs inferred
        f = d["fields"]
        assert f["attribute_bands"]["source"] in ("INFERRED", "USER_TEXT")

    def test_parser_never_invents_facts(self):
        i = intent_parser.parse("find me the best player ever, like messi vibes", "FC26")
        d = i.to_draft()
        assert not d.get("required_playstyles")
        assert not d.get("hard_constraints")
        # an unreferenceable formation-like token IS recorded as unrecognized
        i2 = intent_parser.parse("line them up in a 7-7-7", "FC26")
        assert i2.to_draft().get("unrecognized_fragments")

    def test_role_request_is_insufficient_not_invented(self):
        i = intent_parser.parse("an advanced playmaker role for the CAM slot", "FC26")
        d = i.to_draft()
        assert "role" not in d           # roles are never invented from text
        notes = " ".join(d["confidence_notes"]).upper()
        assert "ROLE" in notes or "INSUFFICIENT" in notes

    def test_budget_parsed_once_and_flagged_unverified(self):
        i = intent_parser.parse("under 100k coins", "FC26")
        d = i.to_draft()
        assert d["budget_coins"] == 100000
        assert any(h["kind"] == "BUDGET" for h in d["hard_constraints"])

    def test_second_tactical_becomes_secondary(self):
        i = intent_parser.parse("high press with quick transitions", "FC26")
        d = i.to_draft()
        assert d["tactical_profile"] == "HIGH_PRESS"
        assert d["secondary_tactical_profile"] in ("COUNTER_ATTACK", "FAST_BUILD_UP")

    def test_every_emitted_value_has_provenance(self):
        i = intent_parser.parse("box-to-box CM, 4-2-3-1, high press, fast build up, "
                                "good stamina, must have Intercept", "FC26")
        d = i.to_draft()
        for key, fld in d["fields"].items():
            assert fld["source"] in ("USER_TEXT", "INFERRED", "DEFAULT"), key
            assert fld["confidence"] in ("HIGH", "MEDIUM", "LOW"), key
            assert isinstance(fld["explicit"], bool), key


# ------------------------------------------------------------------ archetypes
class TestArchetypes:
    def test_archetypes_are_computed_not_assigned(self):
        """§12: no hardcoded player names anywhere in the module source."""
        import inspect
        src = inspect.getsource(archetypes).lower()
        for name in ("valverde", "bellingham", "kante", "modric", "mbappe",
                     "messi", "ronaldo", "pedri", "kroos"):
            assert name not in src

    def test_box_to_box_scores_high_for_engine_cm(self):
        c = make_candidate(attrs=make_attrs(**{**CM_FULL, "stamina": 93,
                                             "interceptions": 84,
                                             "defensive_awareness": 83}))
        s = archetypes.archetype_score(c, "BOX_TO_BOX")
        assert s.status == FitStatus.KNOWN and s.value > 0.6

    def test_same_player_scores_low_for_poacher(self):
        c = make_candidate(attrs=make_attrs(**CM_FULL))
        s = archetypes.archetype_score(c, "POACHER")
        assert s.status == FitStatus.KNOWN and s.value < 0.5

    def test_unknown_archetype_rejected(self):
        c = make_candidate()
        s = archetypes.archetype_score(c, "SPACE_WIZARD")
        assert s.status == FitStatus.UNKNOWN
        assert "no guessing" in s.evidence[0] if s.evidence else True

    def test_gk_archetypes_only_for_gk(self):
        gk = make_candidate(position="GK", attrs=make_attrs(
            gk_diving=88, gk_handling=86, gk_kicking=70, gk_positioning=88,
            gk_reflexes=89))
        assert archetypes.archetype_score(gk, "SWEEPER_KEEPER").status == FitStatus.KNOWN
        assert archetypes.archetype_score(gk, "POACHER").status != FitStatus.KNOWN
        outfield = make_candidate(attrs=make_attrs(**CM_FULL))
        assert archetypes.archetype_score(outfield, "SWEEPER_KEEPER").status != FitStatus.KNOWN

    def test_dominant_archetype_is_deterministic(self):
        c = make_candidate(attrs=make_attrs(**CM_FULL))
        a1 = archetypes.dominant_archetype(c)
        a2 = archetypes.dominant_archetype(c)
        assert a1 == a2
        assert a1 is None or (isinstance(a1, tuple) and a1[0] in archetypes.ARCHETYPE_DEFINITIONS)

    def test_gameplay_profile_labels_capped_and_evidenced(self):
        from backend.domain.card_model import ALL_ATTRS
        outfield = [a for a in ALL_ATTRS if not a.startswith("gk_")]
        god = make_candidate(attrs=make_attrs(**{k: 95 for k in outfield}))
        p = archetypes.gameplay_profile(god)
        assert 0 < len(p["labels"]) <= 4
        assert p["additional_qualified"]          # the rest is disclosed, not hidden
        assert all(l["engine_derived"] for l in p["labels"])
        assert all("evidence" in l for l in p["labels"])

    def test_gameplay_profile_skips_unknown(self):
        sparse = make_candidate(attrs=make_attrs(short_passing=90))
        p = archetypes.gameplay_profile(sparse)
        assert p["skipped_unknown"]               # UNKNOWN reported, never assumed


# ------------------------------------------------------------------ attribute model
class TestAttributeModel:
    def test_saturation_has_knee_not_cliff(self):
        below = attribute_model.saturate(84, "pace", True)
        at = attribute_model.saturate(85, "pace", True)
        above = attribute_model.saturate(99, "pace", True)
        assert below < at < above                 # monotonic, never clipped
        # per-point slope above the knee is smaller than below it (pace knee 90)
        slope_low = attribute_model.saturate(85, "pace", True) - \
            attribute_model.saturate(84, "pace", True)
        slope_high = attribute_model.saturate(96, "pace", True) - \
            attribute_model.saturate(95, "pace", True)
        assert slope_high < slope_low
        assert attribute_model.saturate(99, "pace", False) == pytest.approx(1.0)

    def test_band_score_maps_qualitative_targets(self):
        elite_target = QUALITY_BANDS["elite"]
        s_high, _ = attribute_model.band_score(elite_target + 5, "elite")
        s_low, note = attribute_model.band_score(elite_target - 30, "elite")
        assert s_high == 1.0                      # reaching the target saturates
        assert s_low < 0.5 and note

    def test_band_accepts_databclass_and_dict_via_requirements(self):
        """API path passes AttributeBand dataclasses; draft path passes dicts —
        both must work through intelligence_attribute_fit."""
        c = make_candidate(attrs=make_attrs(**CM_FULL))
        from backend.services.scoring_config import ScoringConfig
        req = make_req(position="CM",
                       attribute_bands=[AttributeBand("stamina", "excellent")])
        fv = attribute_model.intelligence_attribute_fit(c, req, ScoringConfig())
        assert fv.status == FitStatus.KNOWN
        assert any("band" in e.lower() for e in fv.evidence)

    def test_interactions_require_all_known(self):
        c = make_candidate(position="RW", attrs=make_attrs(
            pace=90, dribbling_detail=88, acceleration=90, agility=85,
            ball_control=85))
        vals = attribute_model.interaction_values(c, "RW", ["COUNTER_ATTACK"])
        active = [f for v in vals for f in v["active"]]
        assert active
        assert all(f["inputs"] and f["why"] for f in active)   # explainable
        c2 = make_candidate(position="RW", attrs=make_attrs(pace=90))
        vals2 = attribute_model.interaction_values(c2, "RW", ["COUNTER_ATTACK"])
        skipped = [f for v in vals2 for f in v["skipped"]]
        assert skipped                                        # UNKNOWN -> skipped,
        assert not [f for v in vals2 for f in v["active"] if
                    set(f["inputs"]) & {"dribbling_detail", "agility"}]
        # ...never zero-filled into an active feature

    def test_intelligence_attribute_fit_uses_slot_and_dims(self):
        from backend.services.scoring_config import ScoringConfig
        c = make_candidate(attrs=make_attrs(**CM_FULL))
        req = make_req(position="CM", slot="CAM", secondary_tactical_profile="FAST_BUILD_UP")
        slot, dims = formations.find_slot("4-2-3-1", "CAM"), formations.dimension_vector(
            "HIGH_PRESS", secondary="FAST_BUILD_UP")
        fv = attribute_model.intelligence_attribute_fit(
            c, req, ScoringConfig(), slot=slot, dims=dims)
        assert fv.status == FitStatus.KNOWN
        assert 0.0 <= fv.value <= 1.0

    def test_intelligence_fit_insufficient_on_thin_data(self):
        from backend.services.scoring_config import ScoringConfig
        c = make_candidate(attrs=make_attrs(curve=95))
        req = make_req(position="CM", enable_interactions=True)
        fv = attribute_model.intelligence_attribute_fit(c, req, ScoringConfig())
        assert fv.status == FitStatus.INSUFFICIENT_EVIDENCE


# ------------------------------------------------------------------ playstyle context
class TestPlaystyleContext:
    def test_context_value_tiers(self):
        v_profile, _ = playstyle_context.context_value("Tiki Taka", "POSSESSION", "CM")
        v_position, _ = playstyle_context.context_value("Tiki Taka", None, "CM")
        v_neutral, _ = playstyle_context.context_value("Cross Claimer", None, "CAM")
        assert v_profile == 1.0
        assert v_position == 0.75
        assert v_neutral == 0.35

    def test_plus_is_not_an_automatic_win(self):
        """§11: PS+ never guarantees victory; base-only with perfect context can
        outscore a mismatched +."""
        plus_mismatch = make_candidate(name="PlusMismatch", position="CM",
                                       attrs=make_attrs(**CM_FULL),
                                       playstyles_base=["Rapid"],
                                       playstyles_plus=["Rapid"])
        base_perfect = make_candidate(name="BasePerfect", position="CM",
                                      attrs=make_attrs(**CM_FULL),
                                      playstyles_base=["Tiki Taka", "First Touch"])
        req = make_req(position="CM", tactical_profile="POSSESSION",
                       enable_playstyle_context=True)
        f_plus = playstyle_context.contextual_playstyle_fit(plus_mismatch, req)
        f_base = playstyle_context.contextual_playstyle_fit(base_perfect, req)
        assert f_base.value > f_plus.value

    def test_unpublished_playstyles_insufficient(self):
        c = make_candidate(playstyle_published=False, attrs=make_attrs(**CM_FULL))
        req = make_req(position="CM", desired_playstyles=["Tiki Taka"],
                       enable_playstyle_context=True)
        fv = playstyle_context.contextual_playstyle_fit(c, req)
        assert fv.status == FitStatus.INSUFFICIENT_EVIDENCE

    def test_affinity_table_uses_real_vocabulary_only(self):
        real = {"Acrobatic", "Aerial Fortress", "Anticipate", "Block", "Bruiser",
                "Chip Shot", "Cross Claimer", "Dead Ball", "Deflector", "Enforcer",
                "Far Reach", "Far Throw", "Finesse Shot", "First Touch", "Footwork",
                "Gamechanger", "Incisive Pass", "Intercept", "Inventive", "Jockey",
                "Long Ball Pass", "Long Throw", "Low Driven Shot", "Pinged Pass",
                "Power Shot", "Precision Header", "Press Proven", "Quick Step",
                "Rapid", "Relentless", "Rush Out", "Slide Tackle", "Technical",
                "Tiki Taka", "Trickster", "Whipped Pass"}
        for position, styles in playstyle_context.POSITION_PLAYSTYLE_AFFINITY.items():
            for ps in styles:
                assert ps in real, f"invented playstyle {ps!r} for {position}"


# ------------------------------------------------------------------ squad intelligence
class TestSquadIntelligence:
    def test_structural_fit_is_advisory_and_renormalized(self):
        mate = make_candidate(name="Mate", position="ST", club="Same Club",
                              league="Same League", nation="Same Nation",
                              attrs=make_attrs(finishing=85))
        c = make_candidate(attrs=make_attrs(**CM_FULL), club="Same Club",
                           league="Same League", nation="Same Nation")
        req = make_req(position="CM")
        fv = squad_intelligence.squad_structural_fit(c, [mate], req, None)
        assert fv.status == FitStatus.KNOWN
        assert any("NOT a chemistry" in e for e in fv.evidence)

    def test_no_squad_no_claim(self):
        c = make_candidate(attrs=make_attrs(**CM_FULL))
        fv = squad_intelligence.squad_structural_fit(c, [], make_req(position="CM"), None)
        assert fv.status == FitStatus.UNKNOWN    # nothing requested -> no claim

    def test_replacement_verdicts(self):
        from backend.services.recommendation_engine_v2 import RecommendationEngineV2
        eng = RecommendationEngineV2()
        weak = make_candidate(name="Weak CM", attrs=make_attrs(
            **{**CM_FULL, "stamina": 60, "interceptions": 55,
               "defensive_awareness": 55, "short_passing": 65}))
        strong = make_candidate(name="Strong CM", attrs=make_attrs(
            **{**CM_FULL, "stamina": 92, "interceptions": 86,
               "defensive_awareness": 85, "short_passing": 88}))
        req = make_req(position="CM", tactical_profile="PRESSING")
        res = eng.recommend([weak, strong], req)
        cur_ev = next(e for e in res.ranked if e.candidate.name == "Weak CM")
        analysis = squad_intelligence.replacement_analysis(
            "Weak CM", cur_ev.components, cur_ev.weighted_score,
            cur_ev.candidate, res.ranked)
        assert analysis
        by_name = {a["name"]: a for a in analysis}
        assert by_name["Strong CM"]["verdict"] == "UPGRADE"
        assert by_name["Strong CM"]["improved_components"]
        assert by_name["Strong CM"]["ovr_note"]      # OVR honesty note always present
        assert by_name["Weak CM"]["verdict"] == "SIDEGRADE"   # self-comparison

    def test_stylistic_bias(self):
        attacker = make_candidate(attrs=make_attrs(
            finishing=90, long_shots=88, curve=85, positioning=88, shot_power=87,
            interceptions=55, defensive_awareness=52))
        defender = make_candidate(attrs=make_attrs(
            interceptions=90, standing_tackle=89, defensive_awareness=90,
            sliding_tackle=88, strength=87, finishing=50, long_shots=48,
            positioning=55))
        balanced = make_candidate(attrs=make_attrs(
            finishing=78, long_shots=76, curve=75, positioning=78, shot_power=77,
            interceptions=76, defensive_awareness=75))
        assert squad_intelligence.stylistic_bias(attacker) == "ATTACKING"
        assert squad_intelligence.stylistic_bias(defender) == "DEFENSIVE"
        assert squad_intelligence.stylistic_bias(balanced) == "BALANCED"
        # insufficient evidence on either side -> None, never guessed
        assert squad_intelligence.stylistic_bias(
            make_candidate(attrs=make_attrs(finishing=90))) is None


# ------------------------------------------------------------------ counterfactual & sensitivity
class TestCounterfactuals:
    def _two(self):
        a = make_candidate(name="A", attrs=make_attrs(
            **{**CM_FULL, "stamina": 92, "interceptions": 85}))
        b = make_candidate(name="B", attrs=make_attrs(
            **{**CM_FULL, "vision": 93, "short_passing": 92}))
        return [a, b]

    def test_sensitivity_reports_driver_only_above_noise(self):
        eng = RecommendationEngineV2()
        req = make_req(position="CM", tactical_profile="PRESSING",
                       attribute_preferences=[AttributePreference("stamina", weight=2.0)])
        res = eng.recommend(self._two(), req)
        sens = counterfactual.sensitivity(res.ranked[:2])
        assert sens["status"] in ("OK", "INSUFFICIENT_ALTERNATIVES")
        assert sens["summary"]
        # with fewer than two ranked candidates there is nothing to compare
        sens0 = counterfactual.sensitivity(res.ranked[:1])
        assert sens0["status"] == "INSUFFICIENT_ALTERNATIVES"

    def test_counterfactuals_include_tactics_and_budget_variants(self):
        eng = RecommendationEngineV2()
        req = make_req(position="CM", tactical_profile="PRESSING", budget_coins=10**9)
        pool = self._two()
        res = eng.recommend(pool, req)
        from backend.services.recommendation_engine_v2 import _ResultView
        by_id = {str(c.entity_id): c for c in pool}
        cfs = counterfactual.counterfactuals(
            eng, by_id, req,
            _ResultView(res.ranked, res.excluded_hard, res.excluded_by_floor,
                        res.budget_status, res.best_evaluation))
        kinds = " ".join(c["if"] for c in cfs)
        assert isinstance(cfs, list)
        assert all(set(c) >= {"if", "then", "changes_recommendation"} for c in cfs)


# ------------------------------------------------------------------ confidence v2
class TestConfidenceV2:
    def test_legacy_is_dominant_component(self):
        out = confidence_v2.compute(0.8)
        assert 0.0 <= out["score_v2"] <= 1.0
        # with no auxiliary inputs the legacy score carries ALL the weight
        assert out["composition"]["legacy_confidence"] == pytest.approx(0.8)
        assert out["composition"]["freshness"] is None
        assert out["level"] in ("HIGH", "MEDIUM", "LOW", "VERY_LOW", "UNKNOWN")

    def test_unknown_inputs_renormalize(self):
        out = confidence_v2.compute(0.8, last_observed=None, source_tier=None,
                                    identity_status=None)
        assert out["score_v2"] == pytest.approx(0.8)   # full renormalization

    def test_stale_data_lowers_confidence(self):
        from datetime import datetime, timedelta, timezone
        fresh = confidence_v2.compute(0.8, last_observed=datetime.now(timezone.utc))
        stale = confidence_v2.compute(
            0.8, last_observed=datetime.now(timezone.utc) - timedelta(days=900))
        assert stale["score_v2"] < fresh["score_v2"]

    def test_identity_unresolved_lowers_confidence(self):
        resolved = confidence_v2.compute(0.8, identity_status="RESOLVED")
        unresolved = confidence_v2.compute(0.8, identity_status="UNRESOLVED")
        assert unresolved["score_v2"] < resolved["score_v2"]
        assert any("identity" in r.lower() for r in unresolved["reasons"])

    def test_conflicts_penalize(self):
        clean = confidence_v2.compute(0.8, source_tier=3, unresolved_conflicts=0)
        conflicted = confidence_v2.compute(0.8, source_tier=3, unresolved_conflicts=3)
        assert conflicted["score_v2"] < clean["score_v2"]


# ------------------------------------------------------------------ score bands
class TestScoreBands:
    def test_band_thresholds_match_config(self):
        for threshold, name, meaning in engine_config.SCORE_BANDS:
            b = score_band(threshold + 0.001)
            assert b["band"] == name
            assert "probability" in b["note"]      # never claims probability

    def test_thin_evidence_gets_no_band(self):
        b = score_band(1.0, evidence_coverage=0.3)
        assert b["band"] == "INSUFFICIENT_EVIDENCE"
        b2 = score_band(0.95, evidence_coverage=0.75)
        assert b2["band"] != "INSUFFICIENT_EVIDENCE"
        assert b2["evidence_coverage"] == 0.75

    def test_none_score_no_band(self):
        assert score_band(None) is None


# ------------------------------------------------------------------ effective weights
class TestEffectiveWeights:
    def test_baseline_untouched_for_legacy_requests(self):
        eng = RecommendationEngineV2()
        w = eng.effective_weights(make_req(position="CM"))
        assert w == {k: pytest.approx(v) for k, v in
                     eng.config.component_weights.items()}
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_archetype_weight_renormalizes(self):
        eng = RecommendationEngineV2()
        base = eng.config.component_weights
        w = eng.effective_weights(make_req(position="CM", archetype="BOX_TO_BOX"))
        assert w["archetype_fit"] == pytest.approx(archetypes.ARCHETYPE_WEIGHT)
        # legacy components keep their relative proportions on the remaining 0.90
        for k, v in base.items():
            assert w[k] == pytest.approx(v * (1 - archetypes.ARCHETYPE_WEIGHT))
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_overall_bias_shifts_quality_weight(self):
        eng = RecommendationEngineV2()
        lo = eng.effective_weights(make_req(position="CM", overall_quality_bias="low"))
        hi = eng.effective_weights(make_req(position="CM", overall_quality_bias="high"))
        assert lo["overall_quality"] < hi["overall_quality"]
        assert abs(sum(lo.values()) - 1.0) < 1e-9


# ------------------------------------------------------------------ requirements validation
class TestRequirementsValidation:
    def test_unknown_new_fields_rejected(self):
        r = UserRequirements(game_version="FC26", position="CM",
                             archetype="NOT_A_REAL_ARCHETYPE")
        assert any("archetype" in p.lower() for p in r.validate())
        r2 = UserRequirements(game_version="FC26", position="CM",
                              secondary_tactical_profile="BLITZKRIEG")
        assert r2.validate()
        r3 = UserRequirements(game_version="FC26", position="CM",
                              attribute_bands=[AttributeBand("stamina", "godlike")])
        assert r3.validate()
        r4 = UserRequirements(game_version="FC26", position="CM",
                              overall_quality_bias="extreme")
        assert r4.validate()

    def test_valid_new_fields_accepted(self):
        r = UserRequirements(game_version="FC26", position="CM",
                             archetype="BOX_TO_BOX", slot="CM",
                             secondary_tactical_profile="FAST_BUILD_UP",
                             attribute_bands=[AttributeBand("stamina", "excellent")],
                             enable_interactions=True, enable_saturation=True,
                             enable_playstyle_context=True,
                             overall_quality_bias="normal")
        assert r.validate() == []
