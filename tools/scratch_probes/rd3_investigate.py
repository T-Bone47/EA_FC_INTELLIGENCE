"""Phase 1: RD-3 investigation. Decompose WHY capability correlates with OVR."""
import sys, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.capability_model import compute_capability, saturate
from backend.services.demand_composition import compose_demand
from backend.services.reference_distribution import load_reference_distribution
from backend.services.v3_config import DEFAULT_V3_CONFIG

LAM = DEFAULT_V3_CONFIG.lam_default.value
ref = load_reference_distribution("fc26-players-2026-09-r1")

def spearman(xs, ys):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r=[0]*len(v)
        for p,i in enumerate(o): r[i]=p
        return r
    rx,ry = rank(xs), rank(ys); n=len(xs); mx,my = sum(rx)/n, sum(ry)/n
    num = sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den = (sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

pool = load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})
pool = [c for c in pool if c.overall_rating]

print("="*72)
print("Q1: is capability's correlation with OVR HIGHER or LOWER than raw")
print("    attribute-average correlation with OVR? (i.e. is the ENGINE adding")
print("    correlation beyond what the underlying attribute data already has?)")
demand = compose_demand(position="CM", tactical_profile="POSSESSION", lam=LAM).vector
raw_avg, capability, r_final, ovrs = [], [], [], []
for c in pool:
    vals = [c.attributes.get(a) for a in demand if c.attributes.get(a) is not None]
    if not vals: continue
    raw_avg.append(sum(vals)/len(vals))
    cap = compute_capability(demand=demand, attributes={a: c.attributes.get(a) for a in demand},
                              position="CM", reference=ref)
    capability.append(cap.c_lo)
    ovrs.append(c.overall_rating)
print(f"  rho(raw unweighted attribute average, OVR)     = {spearman(raw_avg, ovrs):+.3f}")
print(f"  rho(capability C_lo [demand-weighted+saturated], OVR) = {spearman(capability, ovrs):+.3f}")
print("  -> if these are close, the correlation is INHERITED from the data,")
print("     not manufactured by demand-weighting or saturation.")

print()
print("="*72)
print("Q2: which attribute FAMILY drives the correlation most?")
FAMILIES = {
    "passing_vision": ["short_passing","long_passing","vision","curve"],
    "physical": ["stamina","strength","aggression","jumping"],
    "dribbling_control": ["ball_control","dribbling_detail","agility","balance"],
    "defensive": ["defensive_awareness","interceptions","standing_tackle","positioning"],
    "pace": ["pace","acceleration","sprint_speed"],
    "mental": ["composure","reactions"],
}
for fam, attrs in FAMILIES.items():
    vals_f, ovrs_f = [], []
    for c in pool:
        v = [c.attributes.get(a) for a in attrs if c.attributes.get(a) is not None]
        if not v: continue
        vals_f.append(sum(v)/len(v)); ovrs_f.append(c.overall_rating)
    if vals_f:
        print(f"  {fam:20s} rho={spearman(vals_f,ovrs_f):+.3f}  (n_attrs_present={len(attrs)})")

print()
print("="*72)
print("Q3: does correlation change across tactical profiles? (structural test:")
print("    if OVR were an independent hidden channel, ALL profiles would")
print("    correlate similarly regardless of what they demand; if it's")
print("    inherited from data, correlation should track how much each")
print("    profile's demand overlaps with the dominant quality axis)")
for prof in ("BALANCED","PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
    d = compose_demand(position="CM", tactical_profile=prof, lam=LAM).vector
    caps, ovrs2 = [], []
    for c in pool:
        cap = compute_capability(demand=d, attributes={a: c.attributes.get(a) for a in d},
                                  position="CM", reference=ref)
        if cap.kappa >= 0.6:
            caps.append(cap.c_lo); ovrs2.append(c.overall_rating)
    print(f"  {prof:12s} rho(C_lo,OVR)={spearman(caps,ovrs2):+.3f}  n={len(caps)}")
