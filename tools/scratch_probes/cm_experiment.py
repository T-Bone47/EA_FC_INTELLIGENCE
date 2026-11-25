"""Experiment CM-1: rebalance build_up_speed/tempo/directness HIGH poles to
reduce passing-family weight, redistributing to pace/directness-specific
attributes. Test against RD-1/RD-2 (CM/CB/ST) AND the full T0/T1 suite
before deciding whether to adopt."""
import sys, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.capability_model import compute_capability
from backend.services.reference_distribution import load_reference_distribution
from backend.services.v3_config import DEFAULT_V3_CONFIG
import backend.services.demand_composition as dc

LAM = DEFAULT_V3_CONFIG.lam_default.value
ref = load_reference_distribution("fc26-players-2026-09-r1")

ORIGINAL = {k: dict(v) for k, v in dc.DIMENSION_HIGH_POLE_AFFINITY.items()}
EXPERIMENT = dict(ORIGINAL)
EXPERIMENT["build_up_speed"] = {"acceleration": 0.30, "sprint_speed": 0.25, "reactions": 0.15,
                                 "short_passing": 0.05, "composure": 0.15, "ball_control": 0.10}
EXPERIMENT["tempo"] = {"reactions": 0.25, "agility": 0.25, "acceleration": 0.20,
                        "stamina": 0.20, "short_passing": 0.05, "composure": 0.05}
EXPERIMENT["directness"] = {"long_shots": 0.25, "heading_accuracy": 0.20, "strength": 0.20,
                             "shot_power": 0.20, "sprint_speed": 0.10, "long_passing": 0.05}

def spearman(xs, ys):
    def rank(v):
        o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for p,i in enumerate(o): r[i]=p
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs); mx,my=sum(rx)/n,sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

def measure(pole_table, position, poolpos):
    dc.DIMENSION_HIGH_POLE_AFFINITY.clear(); dc.DIMENSION_HIGH_POLE_AFFINITY.update(pole_table)
    pool = load_foundation_candidates("FC26", positions=poolpos)
    tops = {}
    for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
        d = dc.compose_demand(position=position, tactical_profile=prof, lam=LAM).vector
        scored = []
        for c in pool:
            cap = compute_capability(demand=d, attributes={a: c.attributes.get(a) for a in d},
                                      position=position, reference=ref)
            if cap.kappa >= 0.6: scored.append((cap.c_lo, c))
        scored.sort(key=lambda t: (-t[0], str(t[1].entity_id)))
        tops[prof] = {c.name for _, c in scored[:10]}
    overlaps = [len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
    pl = len(tops["PRESSING"] & tops["LOW_BLOCK"])
    return sum(overlaps)/len(overlaps), pl

for label, table in (("BASELINE (current v3.0)", ORIGINAL), ("EXPERIMENT CM-1", EXPERIMENT)):
    print(f"\n{label}:")
    for pos, poolpos in (("CM",{"CM","CDM","CAM"}), ("CB",{"CB","LB","RB"}), ("ST",{"ST","LW","RW"})):
        mean_ov, pl = measure(table, pos, poolpos)
        print(f"  {pos:3s} mean_overlap={mean_ov:.2f}/10  PRESS∩LOWBLOCK={pl}/10")

dc.DIMENSION_HIGH_POLE_AFFINITY.clear(); dc.DIMENSION_HIGH_POLE_AFFINITY.update(ORIGINAL)
