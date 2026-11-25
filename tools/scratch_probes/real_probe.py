import sys; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
from backend.domain.user_model import UserRequirements
from backend.services.fit_value import FitStatus
import statistics

eng = RecommendationEngineV2()
pool = load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})
print("pool size:", len(pool))

def run(profile, position="CM", **kw):
    req = UserRequirements(game_version="FC26", position=position,
                           tactical_profile=profile, limit=10, **kw)
    res = eng.recommend(pool, req)
    return res

results={}
for prof in ("PRESSING","POSSESSION","LOW_BLOCK","DIRECT_PLAY","PACE_ABUSER","BALANCED"):
    r = run(prof)
    top = [(e.candidate.name, e.candidate.overall_rating, round(e.weighted_score,4)) for e in r.ranked[:5]]
    results[prof]=top
    print(f"\n--- {prof} top5")
    for t in top: print("   ", t)

# how much does the top-10 set change between profiles?
import itertools
print("\nJaccard overlap of top-10 sets between profiles:")
sets={}
for prof in results: 
    r=run(prof); sets[prof]={e.candidate.name for e in r.ranked[:10]}
for a,b in itertools.combinations(sets,2):
    inter=len(sets[a]&sets[b]); union=len(sets[a]|sets[b])
    print(f"  {a:14s} vs {b:14s}  overlap {inter}/10  jaccard {inter/union:.2f}")
