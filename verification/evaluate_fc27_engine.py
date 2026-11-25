"""Evaluate default rankings and preference invariants on both pinned FC27 releases."""
from argparse import ArgumentParser
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from backend.core import db
from backend.core.config import get_settings
from backend.data_access.candidate_repository import CandidateRepository
from backend.domain.user_model import AttributePreference, UserRequirements
from backend.services.data_license_gate import Environment, environment_from_settings
from backend.services.fc27_card_research import SNAPSHOT, local_release, validate_cached_membership
from backend.services.recommendation_engine_v3 import ENGINE_VERSION, RecommendationEngineV3
from backend.services.reference_distribution import (
    POSITION_GROUPS, position_group_for, resolve_serving_reference,
)
from backend.services.scoring_config import POSITION_ATTRIBUTE_WEIGHTS
from backend.services.v3_config import DEFAULT_V3_CONFIG

PROFILES = ("BALANCED", "HIGH_PRESS", "LOW_BLOCK", "POSSESSION")
DIVISIONS = ("Men's Football", "Women's Football")


def fingerprint(result):
    evidence = [(str(row.context.candidate_entity_id), row.context.r, row.context.r_hi, row.context.coverage_kappa)
                for row in result.ranked]
    return sha256(json.dumps(evidence, separators=(",", ":")).encode()).hexdigest()


def compare_preferences(engine, pool):
    candidate_pool = [c for c in pool if c.position_primary == "ST" or "ST" in c.secondary_positions]
    default = UserRequirements(game_version="FC27", entity_scope="game_player", position="ST",
                               tactical_profile="HIGH_PRESS", limit=10)
    baseline = engine.recommend(candidate_pool, default)
    neutral = engine.recommend(candidate_pool, replace(default, attribute_preferences=[AttributePreference("finishing")]))
    boost = engine.recommend(candidate_pool, replace(default, attribute_preferences=[AttributePreference("finishing", weight=2)]))
    sparse = engine.recommend(candidate_pool, replace(default, attribute_preferences=[AttributePreference("volleys", weight=0.1)]))
    standard = engine.recommend(candidate_pool, replace(default, desired_playstyles_plus=["Quick Step"]))
    messy = engine.recommend(candidate_pool, replace(default, desired_playstyles_plus=["  quick  STEP+ "]))
    return {
        "neutral_weight_1_matches_default": fingerprint(neutral) == fingerprint(baseline),
        "focused_weight_2_default_finishing_weight": baseline.demand.vector.get("finishing", 0.0),
        "focused_weight_2_new_finishing_weight": boost.demand.vector.get("finishing", 0.0),
        "focused_weight_2_changed_top10": fingerprint(boost) != fingerprint(baseline),
        "low_preference_minimum_demand_weight": min(sparse.demand.vector.values()),
        "messy_playstyle_equals_canonical": fingerprint(messy) == fingerprint(standard),
    }


def audit_supplement():
    """Cross-check numeric fields on exact, overall-agreeing item IDs."""
    fields = db.query("""
        WITH items AS (
            SELECT o.record_id, o.normalized, s.manifest->>'schema_version' AS schema
            FROM fc27_staging.observation o JOIN fc27_staging.snapshot s USING(snapshot_id)
            WHERE o.snapshot_id = %s OR s.manifest->>'schema_version' = 'october-item-v1'
        ), linked AS (
            SELECT c.record_id, c.normalized->'attributes' AS card, o.normalized->'attributes' AS supplemental
            FROM items c JOIN items o USING(record_id)
            WHERE c.schema = 'card-item-v1' AND o.schema = 'october-item-v1'
              AND c.normalized->'overall_rating' = o.normalized->'overall_rating'
        )
        SELECT a.key AS attribute, count(*) AS compared, count(*) FILTER (
                WHERE a.value = l.supplemental->a.key) AS exact_agreements,
            count(DISTINCT l.record_id) AS items
        FROM linked l CROSS JOIN LATERAL jsonb_each(l.card) AS a
        WHERE jsonb_typeof(a.value) = 'number' AND jsonb_typeof(l.supplemental->a.key) = 'number'
        GROUP BY a.key ORDER BY a.key
    """, (SNAPSHOT,))
    return {"policy": "Cross-check only. Preserve the frozen serving data and source levels.",
            "comparable_attribute_observations": sum(row["compared"] for row in fields),
            "exact_attribute_agreements": sum(row["exact_agreements"] for row in fields),
            "fields": fields}


def approved_gameplay_count():
    return db.query_one("""
        SELECT count(*) AS n FROM fc27_staging.performance_evidence e
        JOIN fc27_staging.performance_evidence_review r ON r.evidence_id = e.id
        WHERE e.snapshot_id = %s AND e.share_for_research AND r.disposition = 'ACCEPTED'
          AND e.evidence_kind IN ('OWNER_RECORDED_MATCH','USER_SUBMITTED_MATCH','CONTROLLED_EXPERIMENT')
    """, (SNAPSHOT,))["n"]


def evaluate():
    settings = get_settings()
    if environment_from_settings(settings.environment) != Environment.LOCAL:
        raise ValueError("Use the existing local FC27 research database")
    player_ref, _ = resolve_serving_reference("FC27", "game_player", True, Environment.LOCAL)
    players = CandidateRepository().load_candidates("FC27", include_research_only=True)
    card_count = validate_cached_membership()
    card_ref, cards = local_release(settings.database_url)
    assert players and len(cards) == card_count
    player_engine = RecommendationEngineV3(reference=player_ref)
    card_engine = RecommendationEngineV3(reference=card_ref)
    contexts = {}
    for position in sorted(POSITION_ATTRIBUTE_WEIGHTS):
        family = POSITION_GROUPS[position_group_for(position)]
        pools = {
            division: ("game_player", player_engine, [c for c in players if c.extra.get("division") == division
                           and (c.position_primary in family or family.intersection(c.secondary_positions))])
            for division in DIVISIONS
        }
        pools["UT cards"] = ("ut_card", card_engine, [c for c in cards if position in (c.position_primary, *c.secondary_positions)])
        for label, (entity_scope, engine, pool) in pools.items():
            for profile in PROFILES:
                request = UserRequirements(game_version="FC27", entity_scope=entity_scope, position=position,
                                           tactical_profile=profile, limit=10)
                start = perf_counter()
                result = engine.recommend(pool, request)
                elapsed = round((perf_counter() - start) * 1000, 2)
                coverage = [r.context.coverage_kappa for r in result.ranked]
                contexts[f"{label}/{position}/{profile}"] = {
                    "candidates": len(pool), "ranked": len(coverage), "excluded": len(result.excluded),
                    "not_evaluable": len(result.not_evaluable), "min_top10_coverage": min(coverage, default=None),
                    "baseline_fingerprint": fingerprint(result), "engine_ms": elapsed,
                }
    timings = [row["engine_ms"] for row in contexts.values()]
    extra = db.query("""SELECT s.manifest->>'schema_version' AS schema, count(*) AS observations
                      FROM fc27_staging.observation o JOIN fc27_staging.snapshot s USING(snapshot_id)
                      GROUP BY 1 ORDER BY 1""")
    return {
        "engine": ENGINE_VERSION, "config": DEFAULT_V3_CONFIG.config_version,
        "releases": {"players": {"version": player_ref.version, "hash": player_ref.content_hash,
                                 "records": len(players), "division_counts": dict(Counter(c.extra.get("division") for c in players))},
                     "cards": {"version": card_ref.version, "hash": card_ref.content_hash, "records": len(cards)}},
        "staging_observations_by_schema": extra, "accepted_shared_match_records": approved_gameplay_count(),
        "context_count": len(contexts), "median_context_ms": median(timings),
        "preference_checks": compare_preferences(player_engine, players), "contexts": contexts,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--supplement-output", type=Path, help="Write the staged item-attribute reconciliation")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = evaluate()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "contexts"}, indent=2))
    if args.supplement_output:
        args.supplement_output.parent.mkdir(parents=True, exist_ok=True)
        args.supplement_output.write_text(json.dumps(audit_supplement(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
