import sys; sys.path.insert(0,'.')
from backend.tests.helpers import make_candidate, make_req, make_attrs
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
from backend.services.fit_value import FitStatus

def _attrs(**kw): return make_attrs(**kw)
eng = RecommendationEngineV2()

press = make_candidate(name="Press", position="CM", ovr=84, attrs=_attrs(
    stamina=92, aggression=86, interceptions=85, defensive_awareness=83,
    short_passing=78, vision=74))
poss = make_candidate(name="Poss", position="CM", ovr=84, attrs=_attrs(
    stamina=72, aggression=60, interceptions=62, defensive_awareness=68,
    short_passing=90, vision=92))

for profile in ("PRESSING","POSSESSION"):
    req = make_req(position="CM", tactical_profile=profile)
    print("="*70); print("PROFILE", profile)
    eff = eng.effective_weights(req)
    print("declared weights:", eff)
    for c in (press, poss):
        e = eng.evaluate(c, req)
        print(f"-- {c.name}: score={e.weighted_score:.4f} coverage={e.evidence_coverage:.2f}")
        for k,v in e.components.items():
            print(f"     {k:18s} {v.status.value:22s} {('%.4f'%v.value) if v.status==FitStatus.KNOWN else '-'}  effw={e.component_weights.get(k,0):.3f}")
