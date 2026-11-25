"""Phase 2: OVR shuffle / counterfactual audit at scale.
Take real candidates. Freeze every attribute. Randomly permute ONLY the
displayed OVR across the whole pool. If R changes at all, OVR has an
independent channel into the score -- this is the sharpest test available."""
import sys, copy, random; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.recommendation_engine_v3 import RecommendationEngineV3
from backend.services.reference_distribution import load_reference_distribution
from backend.domain.user_model import UserRequirements

ref = load_reference_distribution("fc26-players-2026-09-r1")
engine = RecommendationEngineV3(reference=ref, data_version="fc26-players-2026-09-r1")
pool = load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})[:300]
req = UserRequirements(game_version="FC26", position="CM", tactical_profile="POSSESSION", limit=300)

res_original = engine.recommend(pool, req)
original_scores = {rc.context.candidate_entity_id: rc.context.r for rc in res_original.ranked}
original_order = [rc.context.candidate_entity_id for rc in res_original.ranked]

random.seed(11)
for trial in range(5):
    shuffled = []
    ovrs = [c.overall_rating for c in pool]
    random.shuffle(ovrs)
    for c, new_ovr in zip(pool, ovrs):
        c2 = copy.copy(c)
        c2.overall_rating = new_ovr
        shuffled.append(c2)
    res_shuffled = engine.recommend(shuffled, req)
    shuffled_scores = {rc.context.candidate_entity_id: rc.context.r for rc in res_shuffled.ranked}
    shuffled_order = [rc.context.candidate_entity_id for rc in res_shuffled.ranked]

    max_delta = max(abs(original_scores.get(k,0) - shuffled_scores.get(k,0))
                     for k in set(original_scores) | set(shuffled_scores))
    order_identical = original_order == shuffled_order
    print(f"trial {trial}: max|R_original - R_shuffled_ovr| = {max_delta:.2e}  "
          f"rank order identical: {order_identical}")

print()
print("Extreme case: set every candidate's OVR to the SAME constant (99), attributes untouched")
extreme = []
for c in pool:
    c2 = copy.copy(c); c2.overall_rating = 99; extreme.append(c2)
res_extreme = engine.recommend(extreme, req)
extreme_scores = {rc.context.candidate_entity_id: rc.context.r for rc in res_extreme.ranked}
max_delta_extreme = max(abs(original_scores.get(k,0) - extreme_scores.get(k,0))
                         for k in set(original_scores) | set(extreme_scores))
print(f"  max|R_original - R_all_ovr_99| = {max_delta_extreme:.2e}")
print(f"  rank order identical: {[rc.context.candidate_entity_id for rc in res_extreme.ranked] == original_order}")

print()
print("Reverse case: same OVR (all set to 80), attributes DIFFER (the real, meaningful signal)")
# confirm ranking is NOT flat/degenerate when OVR is constant -- i.e. attributes still discriminate
same_ovr = []
for c in pool:
    c2 = copy.copy(c); c2.overall_rating = 80; same_ovr.append(c2)
res_same_ovr = engine.recommend(same_ovr, req)
distinct_scores = len(set(round(rc.context.r, 6) for rc in res_same_ovr.ranked))
print(f"  candidates ranked: {len(res_same_ovr.ranked)}  distinct scores: {distinct_scores}")
print(f"  (attributes alone produce {distinct_scores} distinct scores among "
      f"{len(res_same_ovr.ranked)} candidates -- confirms scoring is NOT flat "
      f"when OVR is held constant, i.e. attributes are doing the real work)")
