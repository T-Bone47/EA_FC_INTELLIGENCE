"""Phase 6: lambda sweep, 0.0 to 1.0 in steps of 0.1. RD-1/RD-2/RD-3/RD-4
per position, plus T1 guard-case margins, plus INV-1 monotonicity spot check."""
import sys, itertools, json; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.capability_model import compute_capability
from backend.services.demand_composition import compose_demand
from backend.services.reference_distribution import load_reference_distribution
from backend.tests.helpers import make_candidate, make_attrs

ref = load_reference_distribution("fc26-players-2026-09-r1")
POOLS = {
    "CM": load_foundation_candidates("FC26", positions={"CM","CDM","CAM"}),
    "CB": load_foundation_candidates("FC26", positions={"CB","LB","RB"}),
    "ST": load_foundation_candidates("FC26", positions={"ST","LW","RW"}),
}
def spearman(xs, ys):
    def rank(v):
        o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for p,i in enumerate(o): r[i]=p
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs); mx,my=sum(rx)/n,sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

def measure(pos, lam):
    pool = POOLS[pos]
    tops, rhos = {}, []
    for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
        d = compose_demand(position=pos, tactical_profile=prof, lam=lam).vector
        scored = []
        for c in pool:
            cap = compute_capability(demand=d, attributes={a: c.attributes.get(a) for a in d},
                                      position=pos, reference=ref)
            if cap.kappa >= 0.6: scored.append((cap.c_lo, c))
        scored.sort(key=lambda t: (-t[0], str(t[1].entity_id)))
        tops[prof] = {c.name for _, c in scored[:10]}
        if scored:
            rhos.append(spearman([s for s,_ in scored],[c.overall_rating for _,c in scored if c.overall_rating]))
    ov = [len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
    return sum(ov)/len(ov), len(tops["PRESSING"]&tops["LOW_BLOCK"]), min(rhos), max(rhos)

# Guard cases: G-J2 (same shape diff quality) and G-J3 (perfect shape weak level)
POSS = make_attrs(stamina=72, aggression=60, interceptions=62, defensive_awareness=68,
    short_passing=90, vision=92, long_passing=88, ball_control=90, composure=89,
    positioning=80, strength=68, standing_tackle=60, reactions=84, acceleration=74,
    pace=70, long_shots=80, dribbling_detail=86, curve=84, agility=84, balance=82)
def guard_margins(lam):
    from backend.services.recommendation_engine_v3 import RecommendationEngineV3
    from backend.domain.user_model import UserRequirements
    eng = RecommendationEngineV3(reference=ref)
    from dataclasses import replace as dc_replace
    from backend.services.v3_config import DEFAULT_V3_CONFIG, CalibratedValue, CalibrationStatus
    cfg = dc_replace(DEFAULT_V3_CONFIG, lam_default=CalibratedValue(lam, CalibrationStatus.POLICY, "sweep"))
    eng = RecommendationEngineV3(config=cfg, reference=ref)
    req = UserRequirements(game_version="FC26", position="CM", tactical_profile="POSSESSION", limit=5)
    lower_vals = {k: max(1, v-8) for k,v in POSS.values.items()}
    lower = make_candidate(name="Lower80", position="CM", ovr=80, attrs=make_attrs(**lower_vals))
    higher = make_candidate(name="Higher88", position="CM", ovr=88, attrs=POSS)
    res1 = eng.recommend([lower, higher], req)
    g_j2_ok = bool(res1.ranked) and res1.ranked[0].context.candidate_name == "Higher88"
    weak_vals = {k: max(1, int(v*0.62)) for k,v in POSS.values.items()}
    weak = make_candidate(name="PerfectShapeWeak", position="CM", ovr=58, attrs=make_attrs(**weak_vals))
    solid = make_candidate(name="SolidPoss84", position="CM", ovr=84, attrs=POSS)
    res2 = eng.recommend([weak, solid], req)
    g_j3_ok = bool(res2.ranked) and res2.ranked[0].context.candidate_name == "SolidPoss84"
    return g_j2_ok, g_j3_ok

results = []
print(f"{'lam':>4s}  {'pos':3s}  {'mean_ov':>8s}  {'P∩LB':>5s}  {'rho_lo':>7s}  {'rho_hi':>7s}   G-J2  G-J3")
for lam in [round(x*0.1,1) for x in range(0,11)]:
    gj2, gj3 = guard_margins(lam)
    for pos in ("CM","CB","ST"):
        mean_ov, pl, rlo, rhi = measure(pos, lam)
        rd1 = "OK" if mean_ov<=6.0 else "MISS"
        rd2 = "OK" if pl<=4 else "MISS"
        row = dict(lam=lam,pos=pos,mean_overlap=mean_ov,press_lowblock=pl,rho_lo=rlo,rho_hi=rhi,
                   gj2=gj2,gj3=gj3,rd1=rd1,rd2=rd2)
        results.append(row)
        print(f"{lam:>4.1f}  {pos:3s}  {mean_ov:>7.2f}{'*' if mean_ov<=6 else ' '}  {pl:>4d}{'*' if pl<=4 else ' '}  "
              f"{rlo:>7.3f}  {rhi:>7.3f}   {'Y' if gj2 else 'N'}     {'Y' if gj3 else 'N'}")
with open("artifacts/v3_1/calibration/lambda_sweep.json","w") as f:
    json.dump(results, f, indent=2)
