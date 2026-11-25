"""Two-factor model: LEVEL (saturating absolute capability) x SHAPE (level-controlled profile match)."""
import sys, math, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.scoring_config import ScoringConfig, TACTICAL_ATTRIBUTE_WEIGHTS
cfg=ScoringConfig()
def spearman(xs, ys):
    def rank(v):
        o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for p,i in enumerate(o): r[i]=p
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs); mx=sum(rx)/n; my=sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0

pool=[c for c in load_foundation_candidates("FC26",positions={"CM","CDM","CAM"}) if c.overall_rating]
ATTRS=set()
for w in TACTICAL_ATTRIBUTE_WEIGHTS.values(): ATTRS|=set(w)
ATTRS={a for a in ATTRS if not a.startswith("gk_")}
stats={}
for a in ATTRS:
    v=[c.attributes.get(a) for c in pool]; v=[x for x in v if x is not None]
    if len(v)<50: continue
    mu=sum(v)/len(v); sd=(sum((x-mu)**2 for x in v)/len(v))**0.5 or 1.0
    stats[a]=(mu,sd)

def parts(c,w):
    num=den=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None or a not in stats: continue
        mu,sd=stats[a]; num+=wt*((v-mu)/sd); den+=wt
    if not den: return None,None
    demand_z=num/den
    allz=[(c.attributes.get(a)-stats[a][0])/stats[a][1] for a in stats if c.attributes.get(a) is not None]
    level_z=sum(allz)/len(allz) if allz else 0.0
    # LEVEL: absolute demand-weighted capability, saturating
    lev_num=lev_den=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None or a not in stats: continue
        lev_num+=wt*min(v,92)/92.0; lev_den+=wt
    level=lev_num/lev_den
    shape=1/(1+math.exp(-1.6*(demand_z-level_z)))
    return level, shape

for label, comb in (
    ("LEVEL only",                lambda L,S: L),
    ("0.5*L + 0.5*S (additive)",  lambda L,S: 0.5*L+0.5*S),
    ("L * (0.6+0.4*S)  [modifier]",lambda L,S: L*(0.6+0.4*S)),
    ("L^0.65 * S^0.35 [geometric]",lambda L,S: (L**0.65)*(S**0.35)),
):
    print("\n"+"="*70); print(label)
    tops={}
    for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
        w=cfg.tactical_attribute_weights(prof)
        sc=[]
        for c in pool:
            L,S=parts(c,w)
            if L is None: continue
            sc.append((comb(L,S),c))
        sc.sort(key=lambda t:(-t[0],t[1].name))
        tops[prof]={c.name for _,c in sc[:10]}
        print(f"  {prof:12s} rho(OVR)={spearman([s for s,_ in sc],[c.overall_rating for _,c in sc]):+.3f}"
              f" top3={[(c.name,c.overall_rating) for _,c in sc[:3]]}")
    ov=[len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
    print(f"  mean top-10 overlap across tactic pairs: {sum(ov)/len(ov):.1f}/10")
