"""Prototype: separate LEVEL (quality) from SHAPE (tactical fit).
shape_fit = weighted mean of within-pool z-scores, squashed to 0..1.
Compare against the current absolute v/99 formulation."""
import sys, math, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.scoring_config import ScoringConfig, TACTICAL_ATTRIBUTE_WEIGHTS
cfg=ScoringConfig()

def spearman(xs, ys):
    def rank(v):
        order=sorted(range(len(v)), key=lambda i:v[i]); r=[0]*len(v)
        for p,i in enumerate(order): r[i]=p
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs); mx=sum(rx)/n; my=sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

pool=[c for c in load_foundation_candidates("FC26",positions={"CM","CDM","CAM"})
      if c.overall_rating]
ATTRS=set()
for w in TACTICAL_ATTRIBUTE_WEIGHTS.values(): ATTRS|=set(w)
ATTRS={a for a in ATTRS if not a.startswith("gk_")}
# pool statistics (position-scoped)
stats={}
for a in ATTRS:
    vals=[c.attributes.get(a) for c in pool]; vals=[v for v in vals if v is not None]
    if len(vals)<50: continue
    mu=sum(vals)/len(vals); sd=(sum((v-mu)**2 for v in vals)/len(vals))**0.5 or 1.0
    stats[a]=(mu,sd)

def absolute_fit(c,w):
    num=den=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None or a not in stats: continue
        num+=wt*(v/99.0); den+=wt
    return num/den if den else None

def shape_fit(c,w):
    """demand-weighted mean z, minus pool-average z (level removed)."""
    num=den=0.0; zs=[]
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None or a not in stats: continue
        mu,sd=stats[a]; z=(v-mu)/sd
        num+=wt*z; den+=wt; zs.append(z)
    if not den: return None
    # candidate's own general level across the SAME attribute universe
    allz=[(c.attributes.get(a)-stats[a][0])/stats[a][1] for a in stats
          if c.attributes.get(a) is not None]
    level=sum(allz)/len(allz) if allz else 0.0
    rel=(num/den)-level                      # shape only: demand-z minus own level
    return 1/(1+math.exp(-1.6*rel))          # squash to 0..1

for name,fn in (("ABSOLUTE v/99 (current)",absolute_fit),("SHAPE z-relative (proposed)",shape_fit)):
    print("\n"+"="*68); print(name)
    tops={}
    for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
        w=cfg.tactical_attribute_weights(prof)
        scored=[(fn(c,w),c) for c in pool]
        scored=[(s,c) for s,c in scored if s is not None]
        scored.sort(key=lambda t:(-t[0],t[1].name))
        tops[prof]={c.name for _,c in scored[:10]}
        print(f"  {prof:12s} spearman(fit,OVR)={spearman([s for s,_ in scored],[c.overall_rating for _,c in scored]):+.3f}"
              f"  top3={[c.name for _,c in scored[:3]]}")
    print("  --- top-10 overlap between tactics:")
    for a,b in itertools.combinations(tops,2):
        print(f"      {a:12s} vs {b:12s}: {len(tops[a]&tops[b])}/10")
