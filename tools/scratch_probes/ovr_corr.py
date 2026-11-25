import sys; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
from backend.domain.user_model import UserRequirements
eng = RecommendationEngineV2()

def spearman(xs, ys):
    def rank(v):
        order=sorted(range(len(v)), key=lambda i:v[i])
        r=[0]*len(v)
        for pos,i in enumerate(order): r[i]=pos
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs)
    mx=sum(rx)/n; my=sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

for pos, poolpos in (("CM",{"CM","CDM","CAM"}), ("ST",{"ST","LW","RW"}), ("CB",{"CB","LB","RB"})):
    pool = load_foundation_candidates("FC26", positions=poolpos)
    for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER"):
        req=UserRequirements(game_version="FC26",position=pos,tactical_profile=prof,limit=50)
        evals=[eng.evaluate(c,req) for c in pool]
        evals=[e for e in evals if e.rankable and e.candidate.overall_rating]
        s=[e.weighted_score for e in evals]; o=[e.candidate.overall_rating for e in evals]
        print(f"{pos:3s} {prof:12s} n={len(evals):5d}  spearman(score,OVR)={spearman(s,o):+.3f}")
