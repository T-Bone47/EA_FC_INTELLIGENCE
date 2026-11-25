"""T5: do the product-thesis adversarial cases pass under capability-only scoring?
Sweeps lambda (tactical share of the composed demand vector)."""
import sys, math; sys.path.insert(0,'.')
from backend.tests.helpers import make_candidate, make_attrs
from backend.services.scoring_config import ScoringConfig
from backend.services.engine_config import SATURATION_KNEES, DEFAULT_SATURATION_KNEE
cfg=ScoringConfig()
def demand(position, profile, lam):
    pos=cfg.position_attribute_weights(position); tac=cfg.tactical_attribute_weights(profile)
    keys=set(pos)|set(tac)
    w={a:(1-lam)*pos.get(a,0.0)+lam*tac.get(a,0.0) for a in keys}
    w={a:v for a,v in w.items() if v>0 and not a.startswith("gk_")}
    t=sum(w.values()); return {a:v/t for a,v in w.items()}
def sat(v,a):
    k=SATURATION_KNEES.get(a,DEFAULT_SATURATION_KNEE)
    return (v if v<=k else k+(v-k)*0.35)/99.0
def cap(c,w):
    n=d=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None: continue
        n+=wt*sat(v,a); d+=wt
    return (n/d if d else None), d

def A(**kw): return make_attrs(**kw)
CASES=[]
# CASE: LOW_BLOCK RM — 87 attacker vs 82 worker (currently FAILING in v2)
CASES.append(("LOW_BLOCK RM: 87 attacker vs 82 worker","RM","LOW_BLOCK",
  [("Attacker87",87,A(pace=90,dribbling_detail=90,finishing=85,crossing=84,defending=40,
                      interceptions=38,standing_tackle=35,stamina=70,acceleration=88,
                      curve=80,short_passing=72,long_passing=68,agility=86,balance=80,
                      defensive_awareness=40)),
   ("Worker82",82,A(pace=78,dribbling_detail=75,finishing=70,crossing=76,defending=75,
                    interceptions=74,standing_tackle=72,stamina=88,acceleration=76,
                    curve=70,short_passing=76,long_passing=72,agility=74,balance=76,
                    defensive_awareness=76))],"Worker82"))
# CASE: PRESSING vs POSSESSION flip, equal OVR (currently FAILING)
press=A(stamina=92,aggression=86,interceptions=85,defensive_awareness=83,short_passing=78,
        vision=74,long_passing=72,ball_control=76,composure=74,positioning=78,strength=82,
        standing_tackle=84,reactions=82,acceleration=78,pace=76,long_shots=68,
        dribbling_detail=72,curve=66,agility=74,balance=76)
poss=A(stamina=72,aggression=60,interceptions=62,defensive_awareness=68,short_passing=90,
       vision=92,long_passing=88,ball_control=90,composure=89,positioning=80,strength=68,
       standing_tackle=60,reactions=84,acceleration=74,pace=70,long_shots=80,
       dribbling_detail=86,curve=84,agility=84,balance=82)
CASES.append(("PRESSING CM: press-profile vs poss-profile (both 84)","CM","PRESSING",
  [("Press",84,press),("Poss",84,poss)],"Press"))
CASES.append(("POSSESSION CM: press-profile vs poss-profile (both 84)","CM","POSSESSION",
  [("Press",84,press),("Poss",84,poss)],"Poss"))
# CASE: 91 generic vs 83 specialist for POSSESSION CM
CASES.append(("POSSESSION CM: 91 generic vs 83 possession specialist","CM","POSSESSION",
  [("Generic91",91,A(stamina=85,aggression=80,interceptions=78,defensive_awareness=80,
                     short_passing=82,vision=78,long_passing=80,ball_control=82,composure=80,
                     positioning=82,strength=85,standing_tackle=80,reactions=86,
                     acceleration=84,pace=84,long_shots=82,dribbling_detail=82,curve=78,
                     agility=82,balance=80)),
   ("Specialist83",83,A(stamina=76,aggression=62,interceptions=66,defensive_awareness=70,
                        short_passing=93,vision=92,long_passing=90,ball_control=92,
                        composure=91,positioning=80,strength=66,standing_tackle=62,
                        reactions=84,acceleration=72,pace=68,long_shots=78,
                        dribbling_detail=88,curve=88,agility=84,balance=84))],"Specialist83"))
# GUARD CASE: same profile shape, different quality -> higher quality MUST win
CASES.append(("GUARD POSSESSION CM: identical shape, 80 vs 88 quality","CM","POSSESSION",
  [("Lower80",80,A(**{k:max(1,v-8) for k,v in poss.values.items()})),
   ("Higher88",88,poss)],"Higher88"))
# GUARD CASE: excellent shape but far too weak absolutely
weakshape=A(**{k:max(1,int(v*0.62)) for k,v in poss.values.items()})
CASES.append(("GUARD POSSESSION CM: perfect shape at 62% level vs solid 84","CM","POSSESSION",
  [("PerfectShapeWeak",58,weakshape),("SolidPoss84",84,poss)],"SolidPoss84"))

for lam in (0.3,0.5,0.6,0.7,0.8,1.0):
    print(f"\n{'='*74}\nlambda = {lam}")
    allpass=True
    for title,pos,prof,cands,expect in CASES:
        w=demand(pos,prof,lam)
        rows=[]
        for nm,ovr,at in cands:
            c=make_candidate(name=nm,position=pos,ovr=ovr,attrs=at)
            s,cov=cap(c,w); rows.append((s,nm,ovr,cov))
        rows.sort(key=lambda r:-r[0])
        ok = rows[0][1]==expect
        allpass &= ok
        margin=abs(rows[0][0]-rows[1][0])
        print(f"  [{'PASS' if ok else 'FAIL'}] {title[:58]:58s} -> {rows[0][1]:18s} margin={margin:.4f}")
    print(f"  ALL PASS: {allpass}")
