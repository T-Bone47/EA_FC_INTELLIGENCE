"""Probe: does a genuinely bidirectional (signed, two-pole) dimension affinity
fix the PRESSING vs LOW_BLOCK inertness, without breaking monotonicity/dominance?"""
import sys, math, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.formations import PROFILE_DIMENSIONS, DIMENSION_ATTRIBUTE_AFFINITY, dimension_vector
from backend.services.scoring_config import ScoringConfig
cfg = ScoringConfig()

LOW_POLE = {
    "press_intensity": {"defensive_awareness": 0.25, "positioning": 0.20, "standing_tackle": 0.20,
                         "strength": 0.15, "composure": 0.10, "interceptions": 0.10},
    "block_height":    {"standing_tackle": 0.25, "strength": 0.20, "heading_accuracy": 0.20,
                         "jumping": 0.15, "defensive_awareness": 0.15, "aggression": 0.05},
    "build_up_speed":  {"composure": 0.30, "short_passing": 0.25, "vision": 0.20,
                         "long_passing": 0.15, "ball_control": 0.10},
    "directness":      {"short_passing": 0.30, "vision": 0.25, "ball_control": 0.20,
                         "dribbling_detail": 0.15, "composure": 0.10},
    "tempo":           {"strength": 0.25, "composure": 0.25, "positioning": 0.20,
                         "vision": 0.15, "long_passing": 0.15},
    "width":           {"short_passing": 0.30, "vision": 0.25, "defensive_awareness": 0.25,
                         "composure": 0.20},
}

def signed_demand(dims):
    w = {}
    for dim, value in dims.items():
        shift = (value - 0.5) * 2.0
        if abs(shift) < 1e-9: continue
        pole = DIMENSION_ATTRIBUTE_AFFINITY if shift > 0 else LOW_POLE
        mag = abs(shift)
        for attr, aff in pole.get(dim, {}).items():
            w[attr] = w.get(attr, 0.0) + aff*mag
    t = sum(w.values())
    return {a: v/t for a,v in w.items()} if t>0 else {}

def compose(position, profile, lam):
    posw = cfg.position_attribute_weights(position)
    dims = dimension_vector(profile)
    tacw = signed_demand(dims)
    keys = set(posw)|set(tacw)
    w = {a: (1-lam)*posw.get(a,0.0) + lam*tacw.get(a,0.0) for a in keys}
    t = sum(w.values())
    return {a: v/t for a,v in w.items()} if t>0 else posw

def sat(v):
    return (v if v<=88 else 88+(v-88)*0.35)/99.0
def score(c, w):
    n=d=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None: continue
        n+=wt*sat(v); d+=wt
    return n/d if d else None

# --- G-B1/G-B2 direct test: Block vs Pacey CB under LOW_BLOCK then HIGH_PRESS ---
from backend.tests.helpers import make_candidate, make_attrs
block = make_candidate(name="Block", position="CB", ovr=84, attrs=make_attrs(
    defending=89, standing_tackle=88, strength=88, pace=65, short_passing=68,
    defensive_awareness=85, heading_accuracy=82, jumping=80, interceptions=80,
    composure=75, aggression=70, positioning=75, reactions=78))
pacey = make_candidate(name="Pacey", position="CB", ovr=84, attrs=make_attrs(
    defending=80, standing_tackle=80, strength=78, pace=86, short_passing=78,
    defensive_awareness=76, heading_accuracy=72, jumping=76, interceptions=74,
    composure=76, aggression=72, positioning=72, reactions=80))
for lam in (0.5, 0.6, 0.7):
    for prof in ("LOW_BLOCK","HIGH_PRESS"):
        w = compose("CB", prof, lam)
        sb, sp = score(block, w), score(pacey, w)
        winner = "Block" if sb > sp else "Pacey"
        print(f"lam={lam}  {prof:10s}  Block={sb:.4f}  Pacey={sp:.4f}  -> {winner}")
    print()

# --- Real-data tactical discrimination at the EXACT lambda values, including 0.6 ---
print("="*70)
print("REAL DATA: mean top-10 overlap across 5 profiles, exact lambda sweep")
pool = load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})
for lam in (0.3, 0.5, 0.6, 0.7, 1.0):
    tops = {}
    rhos = []
    def spearman(xs, ys):
        def rank(v):
            o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
            for p,i in enumerate(o): r[i]=p
            return r
        rx,ry=rank(xs),rank(ys); n=len(xs); mx=sum(rx)/n; my=sum(ry)/n
        num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
        den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
        return num/den if den else 0.0
    for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
        w = compose("CM", prof, lam)
        sc = [(score(c,w), c) for c in pool]
        sc = [(s,c) for s,c in sc if s is not None]
        sc.sort(key=lambda t:(-t[0], t[1].name))
        tops[prof] = {c.name for _,c in sc[:10]}
        rhos.append(spearman([s for s,_ in sc],[c.overall_rating for _,c in sc]))
    ov = [len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
    pl_lb = len(tops["PRESSING"] & tops["LOW_BLOCK"])
    print(f"lam={lam:.1f}  mean_overlap={sum(ov)/len(ov):.1f}/10  "
          f"PRESSING∩LOW_BLOCK={pl_lb}/10  rho_range=[{min(rhos):+.2f},{max(rhos):+.2f}]")

print("\n" + "="*70)
print("DIAGNOSIS: why doesn't Pacey win under HIGH_PRESS at CB?")
print("HIGH_PRESS dims:", dimension_vector("HIGH_PRESS"))
print("LOW_BLOCK dims:", dimension_vector("LOW_BLOCK"))
w_hp = compose("CB", "HIGH_PRESS", 0.7)
w_lb = compose("CB", "LOW_BLOCK", 0.7)
print("\nCB/HIGH_PRESS composed demand (lam=0.7), sorted by weight:")
for a,v in sorted(w_hp.items(), key=lambda kv:-kv[1])[:12]:
    print(f"   {a:22s} {v:.4f}   Block={block.attributes.get(a)}  Pacey={pacey.attributes.get(a)}")
print("\nCB/LOW_BLOCK composed demand (lam=0.7), sorted by weight:")
for a,v in sorted(w_lb.items(), key=lambda kv:-kv[1])[:12]:
    print(f"   {a:22s} {v:.4f}   Block={block.attributes.get(a)}  Pacey={pacey.attributes.get(a)}")
print("\nCB position base weights (lam=0 equivalent), top 10:")
for a,v in sorted(cfg.position_attribute_weights("CB").items(), key=lambda kv:-kv[1])[:10]:
    print(f"   {a:22s} {v:.4f}")
