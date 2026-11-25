import sys; sys.path.insert(0,'.')
from backend.tests.helpers import make_candidate, make_req, make_attrs
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
eng=RecommendationEngineV2()
CB=dict(defending=86, standing_tackle=85, interceptions=84, heading_accuracy=82,
        strength=86, defensive_awareness=85, jumping=80, aggression=80, reactions=82,
        pace=70, short_passing=70, long_passing=66, vision=62, composure=78)
ST=dict(finishing=92, positioning=90, shot_power=88, pace=90, composure=88,
        heading_accuracy=80, volleys=85, long_shots=84, strength=78, agility=88,
        ball_control=88, acceleration=90, reactions=90, dribbling_detail=88,
        defending=30, standing_tackle=25, interceptions=28, defensive_awareness=30,
        jumping=70, aggression=55)
cb  = make_candidate(name="RealCB85", position="CB", ovr=85, attrs=make_attrs(**CB))
st  = make_candidate(name="StrikerPlayedAtCB91", position="ST", ovr=91, attrs=make_attrs(**ST))
res = eng.recommend([cb, st], make_req(position="CB", tactical_profile="LOW_BLOCK"))
for i,e in enumerate(res.ranked,1):
    print(f"{i}. {e.candidate.name:22s} score={e.weighted_score:.4f} "
          f"pos_fit={e.components['position_fit'].value:.2f} "
          f"attr={e.components['attribute_fit'].value:.3f} "
          f"tac={e.components['tactical_fit'].value:.3f}")
print("excluded_hard:", res.excluded_hard)
