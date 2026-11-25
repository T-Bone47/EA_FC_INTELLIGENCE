"""Exercise the owner-supplied FC27 player snapshot in local research mode."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.domain.card_model import Candidate, DataStatus
from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.domain.user_model import UserRequirements
from backend.ingestion import fc27_research_profile as profile
from backend.ingestion.ea_ratings_csv_adapter import EARatingsCsvAdapter, file_sha256
from backend.ingestion.normalizer import Normalizer
from backend.services.data_license_gate import Environment
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import resolve_serving_reference
from backend.services.scoring_context import reconstruct_score

assert file_sha256(profile.RAW_PLAYERS_CSV) == profile.PLAYERS_CSV_SHA256
source = SourceRecord(profile.SOURCE_ID, "FC27 player ratings", "CARRIER_DATASET", 4,
                      usage_status=UsageStatus.RESEARCH_ONLY, legal_gate="CLEARED")
adapter = EARatingsCsvAdapter(source, "FC27", profile.RAW_PLAYERS_CSV)
normalizer = Normalizer(source.source_id, "FC27")
playstyles = defaultdict(list)
for row in adapter.fetch_playstyles():
    playstyles[row.source_player_id].append(row)
groups = defaultdict(list)
divisions = Counter()
for raw in adapter.fetch_players():
    player = normalizer.normalize_player(raw)
    player.data_status = DataStatus.RESEARCH_ONLY
    styles = playstyles[raw.source_player_id]
    player.playstyles_base = [item.playstyle for item in styles if item.tier == "base"]
    player.playstyles_plus = [item.playstyle for item in styles if item.tier == "plus"]
    player.playstyle_data_published = bool(styles)
    candidate = Candidate.from_game_player(player)
    groups[(player.gender, player.position_primary)].append(candidate)
    divisions[player.gender] += 1

ref, research = resolve_serving_reference("FC27", "game_player", True, Environment.RESEARCH)
assert research and sum(divisions.values()) == profile.EXPECTED_ROW_COUNT
engine = RecommendationEngineV3(reference=ref, data_version=ref.version)
rng = random.Random(27)
results = []
for division in ("Men's Football", "Women's Football"):
    for position in profile.POSITION_VOCABULARY:
        pool = groups[(division, position)]
        sample = rng.sample(pool, min(24, len(pool)))
        for tactic in ("BALANCED", "POSSESSION", "HIGH_PRESS", "LOW_BLOCK", "COUNTER_ATTACK", "DIRECT_PLAY"):
            request = UserRequirements(position=position, game_version="FC27", tactical_profile=tactic,
                                       entity_scope="game_player", limit=10)
            ranked = engine.recommend(sample, request).ranked
            reversed_ranked = engine.recommend(list(reversed(sample)), request).ranked
            assert ranked and all(abs(reconstruct_score(row.context) - row.context.r) <= 1e-9 for row in ranked)
            assert [(row.context.candidate_entity_id, row.context.r) for row in ranked] == [
                (row.context.candidate_entity_id, row.context.r) for row in reversed_ranked]
            results.append({"division": division, "position": position, "tactic": tactic, "sample": len(sample)})
output = {"status": "PASS", "scope": "offline local research; division pools formed by the audit script",
          "reference": ref.version, "divisions": divisions, "cases": results}
Path(__file__).with_name("FC27_ENGINE_RESULTS.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(f"PASS {len(results)} FC27 division/position/tactic combinations")
