"""PHASE 14 — measure v3 evidence-coverage kappa on the real FC26 foundation."""
import sys, statistics; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.scoring_config import ScoringConfig
cfg=ScoringConfig(); LAM=0.6
def demand(pos,prof,lam=LAM):
    p=cfg.position_attribute_weights(pos); t=cfg.tactical_attribute_weights(prof)
    w={a:(1-lam)*p.get(a,0.0)+lam*t.get(a,0.0) for a in set(p)|set(t)}
    isgk = pos=="GK"
    w={a:v for a,v in w.items() if v>0 and (a.startswith("gk_")==isgk)}
    s=sum(w.values()); return {a:v/s for a,v in w.items()} if s else {}
def q(vals,p):
    vals=sorted(vals); 
    if not vals: return None
    i=min(len(vals)-1,max(0,int(round(p*(len(vals)-1)))))
    return vals[i]
POSGROUPS={"GK":{"GK"},"DEF":{"CB","LB","RB"},"MID":{"CDM","CM","CAM","LM","RM"},"ATT":{"LW","RW","ST"}}
print(f"{'pos':4s} {'profile':12s} {'n':>6s} {'|D|':>4s}  P01   P05   P10   P25   P50   P75   P90   P99")
rows=[]
for pos,prof in (("CM","POSSESSION"),("CM","PRESSING"),("CB","LOW_BLOCK"),("ST","COUNTER_ATTACK"),
                 ("RW","CROSSING"),("LB","BUILD_UP"),("GK","BUILD_UP")):
    grp=next(g for g,s in POSGROUPS.items() if pos in s)
    pool=load_foundation_candidates("FC26",positions=POSGROUPS[grp])
    w=demand(pos,prof)
    ks=[]
    for c in pool:
        k=sum(wt for a,wt in w.items() if c.attributes.get(a) is not None)
        ks.append(k)
    rows.append((pos,prof,ks))
    print(f"{pos:4s} {prof:12s} {len(ks):6d} {len(w):4d}  " +
          "  ".join(f"{q(ks,p):.2f}" for p in (.01,.05,.10,.25,.50,.75,.90,.99)))
print()
print("Share of candidates EVALUABLE at each kappa_min threshold:")
print(f"{'pos/profile':26s}" + "".join(f"{t:>9.2f}" for t in (0.40,0.50,0.60,0.70,0.80,0.90,1.00)))
for pos,prof,ks in rows:
    line=f"{pos+'/'+prof:26s}"
    for t in (0.40,0.50,0.60,0.70,0.80,0.90,1.00):
        line+=f"{sum(1 for k in ks if k>=t)/len(ks)*100:8.1f}%"
    print(line)
