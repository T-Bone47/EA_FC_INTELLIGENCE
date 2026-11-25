import sys; sys.path.insert(0,'.')
from backend.tests.helpers import make_candidate, make_req, make_attrs
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
eng=RecommendationEngineV2()
FULL=dict(short_passing=88, vision=86, long_passing=85, stamina=90, ball_control=87,
          composure=86, defensive_awareness=80, interceptions=78, positioning=80,
          dribbling_detail=82, strength=80, long_shots=78)
thick = make_candidate(name="WellDocumented84", ovr=84, attrs=make_attrs(**FULL))
thin  = make_candidate(name="UndocumentedSameOVR", ovr=84, attrs=make_attrs(short_passing=60))
thin2 = make_candidate(name="UndocumentedLowOVR", ovr=80, attrs=make_attrs(short_passing=55))
req = make_req(position="CM", tactical_profile="POSSESSION")
res = eng.recommend([thick, thin, thin2], req)
print("RANKING (POSSESSION CM):")
for i,e in enumerate(res.ranked,1):
    print(f" {i}. {e.candidate.name:22s} score={e.weighted_score:.4f} "
          f"coverage={e.evidence_coverage:.2f} band={e.score_band['band']}")
print("\nconfidence of winner:", round(res.best_evaluation.confidence.score,3))
print("winner known components:", res.best_evaluation.confidence.known_components)
