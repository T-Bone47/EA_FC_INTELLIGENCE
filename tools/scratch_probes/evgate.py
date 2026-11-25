"""Evidence gating: rank on the LOWER bound of the evidence interval.
Missing demand weight is charged at a pool-derived pessimistic bound, never redistributed."""
import sys; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.tests.helpers import make_candidate, make_attrs
from backend.services.scoring_config import ScoringConfig
from backend.services.engine_config import SATURATION_KNEES, DEFAULT_SATURATION_KNEE
cfg=ScoringConfig(); LAM=0.6
POOL=[c for c in load_foundation_candidates("FC26",positions={"CM","CDM","CAM"}) if c.overall_rating]
def demand(pos,prof,lam=LAM):
    p=cfg.position_attribute_weights(pos); t=cfg.tactical_attribute_weights(prof)
    w={a:(1-lam)*p.get(a,0.0)+lam*t.get(a,0.0) for a in set(p)|set(t)}
    w={a:v for a,v in w.items() if v>0 and not a.startswith("gk_")}
    s=sum(w.values()); return {a:v/s for a,v in w.items()}
def sat(v,a):
    k=SATURATION_KNEES.get(a,DEFAULT_SATURATION_KNEE)
    return (v if v<=k else k+(v-k)*0.35)/99.0
# frozen pool quantiles (precomputed per position x version in production)
def quantiles(pool,attrs,qlo=0.10,qhi=0.90):
    out={}
    for a in attrs:
        v=sorted(x for x in (c.attributes.get(a) for c in pool) if x is not None)
        if len(v)<50: continue
        out[a]=(v[int(qlo*len(v))], v[int(qhi*len(v))])
    return out
W=demand("CM","POSSESSION"); Q=quantiles(POOL,list(W))
COVERAGE_FLOOR=0.60
def evidence_scored(c,w=W):
    lo=hi=cov=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None:
            if a in Q: lo+=wt*sat(Q[a][0],a); hi+=wt*sat(Q[a][1],a)
            else: hi+=wt
            continue
        s=sat(v,a); lo+=wt*s; hi+=wt*s; cov+=wt
    return lo,hi,cov

FULL=dict(short_passing=88,vision=86,long_passing=85,stamina=90,ball_control=87,
          composure=86,defensive_awareness=80,interceptions=78,positioning=80,
          dribbling_detail=82,strength=80,long_shots=78,curve=80,agility=80,
          balance=80,reactions=84,acceleration=76,pace=74,aggression=70,
          standing_tackle=70)
cands=[make_candidate(name="WellDocumented84",ovr=84,attrs=make_attrs(**FULL)),
       make_candidate(name="UndocumentedSameOVR",ovr=84,attrs=make_attrs(short_passing=60)),
       make_candidate(name="UndocumentedLowOVR",ovr=80,attrs=make_attrs(short_passing=55)),
       make_candidate(name="PartialGoodEvidence",ovr=84,attrs=make_attrs(
           short_passing=90,vision=88,ball_control=89,composure=88,long_passing=86,
           dribbling_detail=84,positioning=80,curve=82,agility=82,reactions=84))]
print(f"demand attrs={len(W)}  coverage floor={COVERAGE_FLOOR}\n")
rows=[]
for c in cands:
    lo,hi,cov=evidence_scored(c)
    rows.append((lo,hi,cov,c.name,c.overall_rating))
rows.sort(key=lambda r:-r[0])
print(f"{'candidate':24s} {'OVR':>4s} {'cov':>6s} {'rank_lo':>8s} {'upper':>7s}  status")
for lo,hi,cov,nm,ovr in rows:
    st = "RANKED" if cov>=COVERAGE_FLOOR else "NOT_EVALUABLE (below coverage floor)"
    print(f"{nm:24s} {ovr:4d} {cov:6.2f} {lo:8.4f} {hi:7.4f}  {st}")
print("\nv2 behaviour for the same pool was: UndocumentedSameOVR ranked #1 (score 0.8919).")
