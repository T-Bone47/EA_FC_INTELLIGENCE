"""V3 candidate-formulation stress test.
Compares: A) v2 composite  B) capability-only  C) capability x shape modifier.
Axes: tactical discrimination, rho(OVR), Pareto dominance, pool dependence, monotonicity."""
import sys, math, itertools, random; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.scoring_config import ScoringConfig, TACTICAL_ATTRIBUTE_WEIGHTS
from backend.services.engine_config import SATURATION_KNEES, DEFAULT_SATURATION_KNEE
cfg = ScoringConfig()
random.seed(7)

def spearman(xs, ys):
    def rank(v):
        o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for p,i in enumerate(o): r[i]=p
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs); mx=sum(rx)/n; my=sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

POOL = [c for c in load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})
        if c.overall_rating]

def demand(position, profile, lam):
    """Composed demand: (1-lam)*position base + lam*tactical. Both normalized first."""
    pos = cfg.position_attribute_weights(position)
    tac = cfg.tactical_attribute_weights(profile)
    keys = set(pos) | set(tac)
    w = {a: (1-lam)*pos.get(a,0.0) + lam*tac.get(a,0.0) for a in keys}
    w = {a:v for a,v in w.items() if v > 0 and not a.startswith("gk_")}
    t = sum(w.values())
    return {a: v/t for a,v in w.items()}

def sat(v, a):
    k = SATURATION_KNEES.get(a, DEFAULT_SATURATION_KNEE)
    return (v if v <= k else k + (v-k)*0.35) / 99.0

def capability(c, w):
    num=den=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None: continue
        num += wt*sat(v,a); den += wt
    return (num/den, den) if den else (None, 0.0)

# ---- pool statistics for the shape term (z-scores) ----
def pool_stats(pool, attrs):
    st={}
    for a in attrs:
        vals=[c.attributes.get(a) for c in pool]; vals=[v for v in vals if v is not None]
        if len(vals)<50: continue
        mu=sum(vals)/len(vals); sd=(sum((v-mu)**2 for v in vals)/len(vals))**0.5 or 1.0
        st[a]=(mu,sd)
    return st

ALLATTR=set()
for t in TACTICAL_ATTRIBUTE_WEIGHTS.values(): ALLATTR |= set(t)
for p in ("CM","CDM","CAM"): ALLATTR |= set(cfg.position_attribute_weights(p))
ALLATTR={a for a in ALLATTR if not a.startswith("gk_")}
STATS = pool_stats(POOL, ALLATTR)

def shape(c, w, stats):
    num=den=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None or a not in stats: continue
        mu,sd=stats[a]; num+=wt*((v-mu)/sd); den+=wt
    if not den: return None
    dz=num/den
    allz=[(c.attributes.get(a)-stats[a][0])/stats[a][1] for a in stats
          if c.attributes.get(a) is not None]
    gz=sum(allz)/len(allz) if allz else 0.0
    return 1/(1+math.exp(-1.6*(dz-gz)))

def F_capability(c, w, stats=None):
    cap,_=capability(c,w); return cap
def F_shape_mod(c, w, stats):
    cap,_=capability(c,w)
    if cap is None: return None
    s=shape(c,w,stats)
    return cap*(0.6+0.4*s) if s is not None else None

FORMS={"B_capability_only":F_capability, "C_capability_x_shape":F_shape_mod}
PROFILES=("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY")

print("="*76); print("T1/T2  TACTICAL DISCRIMINATION + OVR CORRELATION  (lambda = tactical share)")
for lam in (0.0, 0.3, 0.5, 0.7, 1.0):
    for fname,fn in FORMS.items():
        tops={}; rhos=[]
        for prof in PROFILES:
            w=demand("CM",prof,lam)
            sc=[(fn(c,w,STATS),c) for c in POOL]
            sc=[(s,c) for s,c in sc if s is not None]
            sc.sort(key=lambda t:(-t[0],t[1].name))
            tops[prof]={c.name for _,c in sc[:10]}
            rhos.append(spearman([s for s,_ in sc],[c.overall_rating for _,c in sc]))
        ov=[len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
        print(f"  lam={lam:.1f} {fname:22s} mean top10 overlap={sum(ov)/len(ov):4.1f}/10  "
              f"rho(OVR) range=[{min(rhos):+.2f},{max(rhos):+.2f}]")
    print()

print("="*76); print("T3  PARETO DOMINANCE VIOLATIONS  (A >= B on every demand attribute => score(A) >= score(B))")
w = demand("CM","PRESSING",0.6)
dattrs=sorted(w)
pairs=0; viol={"B_capability_only":0,"C_capability_x_shape":0}
sample=random.sample(POOL, 900)
for a,b in itertools.combinations(sample, 2):
    va=[a.attributes.get(x) for x in dattrs]; vb=[b.attributes.get(x) for x in dattrs]
    if any(v is None for v in va+vb): continue
    if all(x>=y for x,y in zip(va,vb)) and any(x>y for x,y in zip(va,vb)):
        pairs+=1
        for fname,fn in FORMS.items():
            sa,sb=fn(a,w,STATS),fn(b,w,STATS)
            if sa is not None and sb is not None and sa < sb - 1e-12:
                viol[fname]+=1
print(f"  dominating pairs found: {pairs}")
for f in viol:
    rate = viol[f]/pairs*100 if pairs else 0
    print(f"  {f:22s} violations={viol[f]:4d}  ({rate:.2f}%)")

print()
print("="*76); print("T6  MONOTONICITY  (raise one attribute by +5, score must not fall)")
import copy
from backend.domain.card_model import PlayerAttributes
def bump(c, attr, d=5):
    import copy as _c
    c2=_c.copy(c); pa=PlayerAttributes(); pa.values=dict(c.attributes.values)
    if pa.values.get(attr) is None: return None
    pa.values[attr]=min(99, pa.values[attr]+d); c2.attributes=pa
    c2.feature_cache={} if hasattr(c,'feature_cache') else None
    return c2
test_attrs = sorted(ALLATTR)
drops={"B_capability_only":0,"C_capability_x_shape":0}
checks=0
for c in random.sample(POOL, 120):
    for attr in test_attrs:
        c2=bump(c,attr)
        if c2 is None: continue
        checks+=1
        for fname,fn in FORMS.items():
            s1,s2=fn(c,w,STATS),fn(c2,w,STATS)
            if s1 is not None and s2 is not None and s2 < s1 - 1e-12:
                drops[fname]+=1
print(f"  perturbations checked: {checks}")
for f in drops:
    print(f"  {f:22s} score DECREASED on {drops[f]:5d} ({drops[f]/checks*100:.1f}%) improvements")

print()
print("="*76); print("T4  POOL DEPENDENCE  (does changing the candidate pool change a player's score?)")
NARROW=[c for c in POOL if c.position_primary=="CM"]
ST_N = pool_stats(NARROW, ALLATTR)
common=[c for c in NARROW if c.attributes.get("stamina") is not None][:400]
for fname,fn in FORMS.items():
    s_wide=[fn(c,w,STATS) for c in common]
    s_narrow=[fn(c,w,ST_N) for c in common]
    pairs=[(a,b) for a,b in zip(s_wide,s_narrow) if a is not None and b is not None]
    maxdelta=max(abs(a-b) for a,b in pairs)
    rho=spearman([a for a,_ in pairs],[b for _,b in pairs])
    # rank churn in top 20
    rw=sorted(range(len(pairs)), key=lambda i:-pairs[i][0])[:20]
    rn=sorted(range(len(pairs)), key=lambda i:-pairs[i][1])[:20]
    print(f"  {fname:22s} max|score delta|={maxdelta:.4f}  rank corr={rho:+.4f}  top20 overlap={len(set(rw)&set(rn))}/20")
