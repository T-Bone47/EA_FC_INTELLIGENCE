import sys, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.capability_model import compute_capability
from backend.services.demand_composition import compose_demand
from backend.services.reference_distribution import load_reference_distribution
from backend.services.v3_config import DEFAULT_V3_CONFIG

def kendall_tau(xs, ys, sample_cap=2000):
    import random
    n = len(xs)
    idx = list(range(n))
    if n > 200:  # O(n^2) -- subsample for tractability
        random.seed(3); idx = random.sample(idx, 200)
    conc = disc = 0
    for i, j in itertools.combinations(idx, 2):
        dx = xs[i]-xs[j]; dy = ys[i]-ys[j]
        if dx*dy > 0: conc += 1
        elif dx*dy < 0: disc += 1
    total = conc+disc
    return (conc-disc)/total if total else 0.0

ref = load_reference_distribution("fc26-players-2026-09-r1")
LAM = DEFAULT_V3_CONFIG.lam_default.value
pool = load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})
pool = [c for c in pool if c.overall_rating]
demand = compose_demand(position="CM", tactical_profile="POSSESSION", lam=LAM).vector
caps, ovrs = [], []
for c in pool:
    cap = compute_capability(demand=demand, attributes={a: c.attributes.get(a) for a in demand},
                              position="CM", reference=ref)
    if cap.kappa >= 0.6:
        caps.append(cap.c_lo); ovrs.append(c.overall_rating)
print(f"Kendall tau(R, OVR), CM/POSSESSION, n=200 subsample: {kendall_tau(caps, ovrs):+.3f}")

print()
print("="*72)
print("PHASE 3: CM demand vector decomposition across all 6 profiles")
print("="*72)
for prof in ("BALANCED","PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
    posw = __import__("backend.services.scoring_config", fromlist=["ScoringConfig"]).ScoringConfig().position_attribute_weights("CM")
    from backend.services.demand_composition import signed_tactical_demand
    tacw = signed_tactical_demand(prof)
    d = compose_demand(position="CM", tactical_profile=prof, lam=LAM)
    print(f"\n--- {prof} (tactical_demand_neutral={d.tactical_demand_neutral}) ---")
    top = sorted(d.vector.items(), key=lambda kv: -kv[1])[:8]
    for attr, w in top:
        base = posw.get(attr, 0.0)
        tac = tacw.get(attr, 0.0)
        base_norm = base / sum(posw.values()) if sum(posw.values()) else 0
        print(f"  {attr:20s} final={w:.4f}  position_base={base_norm:.4f}  tactical_pure={tac:.4f}")
