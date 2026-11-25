"""Iterate: construct a fair CB pair that differs mainly on the pace/recovery-speed
vs duel-discipline axis, with comparable overall quality (not one card dominating
everything), and confirm the HIGH_PRESS/LOW_BLOCK flip at lambda=0.6."""
import sys, math, itertools; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.services.formations import DIMENSION_ATTRIBUTE_AFFINITY, dimension_vector
from backend.services.scoring_config import ScoringConfig
from backend.tests.helpers import make_candidate, make_attrs
cfg = ScoringConfig()

# Slightly stronger recovery-pace affinity on the HIGH pole of block_height/press_intensity
# (the football claim "a high line lives on CB recovery speed" is a materially stronger
# effect than the v2 table gave it credit for -- this IS an engine convention, labelled
# as such, not a verified mechanic).
HIGH_POLE_OVERRIDE = dict(DIMENSION_ATTRIBUTE_AFFINITY)
HIGH_POLE_OVERRIDE["block_height"] = {"pace": 0.35, "acceleration": 0.25, "reactions": 0.15,
                                       "defensive_awareness": 0.10, "positioning": 0.10, "interceptions": 0.05}
HIGH_POLE_OVERRIDE["press_intensity"] = {"stamina": 0.25, "aggression": 0.20, "interceptions": 0.20,
                                          "reactions": 0.15, "acceleration": 0.10, "positioning": 0.10}
LOW_POLE = {
    "press_intensity": {"defensive_awareness": 0.25, "positioning": 0.20, "standing_tackle": 0.20,
                         "strength": 0.15, "composure": 0.10, "interceptions": 0.10},
    "block_height":    {"standing_tackle": 0.30, "strength": 0.25, "heading_accuracy": 0.20,
                         "jumping": 0.15, "defensive_awareness": 0.10},
    "build_up_speed":  {"composure": 0.30, "short_passing": 0.25, "vision": 0.20,
                         "long_passing": 0.15, "ball_control": 0.10},
    "directness":      {"short_passing": 0.30, "vision": 0.25, "ball_control": 0.20,
                         "dribbling_detail": 0.15, "composure": 0.10},
    "tempo":           {"strength": 0.25, "composure": 0.25, "positioning": 0.20,
                         "vision": 0.15, "long_passing": 0.15},
    "width":           {"short_passing": 0.30, "vision": 0.25, "defensive_awareness": 0.25,
                         "composure": 0.20},
}
def signed_demand(dims, high_table):
    w = {}
    for dim, value in dims.items():
        shift = (value - 0.5) * 2.0
        if abs(shift) < 1e-9: continue
        pole = high_table if shift > 0 else LOW_POLE
        mag = abs(shift)
        for attr, aff in pole.get(dim, {}).items():
            w[attr] = w.get(attr, 0.0) + aff*mag
    t = sum(w.values())
    return {a: v/t for a,v in w.items()} if t>0 else {}

def compose(position, profile, lam, high_table):
    posw = cfg.position_attribute_weights(position)
    dims = dimension_vector(profile)
    tacw = signed_demand(dims, high_table)
    keys = set(posw)|set(tacw)
    w = {a: (1-lam)*posw.get(a,0.0) + lam*tacw.get(a,0.0) for a in keys}
    t = sum(w.values())
    return {a: v/t for a,v in w.items()} if t>0 else posw

def sat(v): return (v if v<=88 else 88+(v-88)*0.35)/99.0
def score(c, w):
    n=d=0.0
    for a,wt in w.items():
        v=c.attributes.get(a)
        if v is None: continue
        n+=wt*sat(v); d+=wt
    return n/d if d else None

COMMON = dict(stamina=76, aggression=70, composure=78, vision=60, short_passing=70,
              long_passing=64, ball_control=68, dribbling_detail=55)
block = make_candidate(name="Block", position="CB", ovr=84, attrs=make_attrs(
    defending=85, standing_tackle=86, strength=87, pace=64, acceleration=63,
    defensive_awareness=84, heading_accuracy=83, jumping=82, interceptions=82,
    positioning=80, reactions=74, **COMMON))
pacey = make_candidate(name="Pacey", position="CB", ovr=84, attrs=make_attrs(
    defending=82, standing_tackle=80, strength=76, pace=89, acceleration=88,
    defensive_awareness=79, heading_accuracy=74, jumping=76, interceptions=78,
    positioning=76, reactions=84, **COMMON))

for lam in (0.5, 0.6, 0.7):
    for prof in ("LOW_BLOCK","HIGH_PRESS"):
        w = compose("CB", prof, lam, HIGH_POLE_OVERRIDE)
        sb, sp = score(block, w), score(pacey, w)
        print(f"lam={lam}  {prof:10s}  Block={sb:.4f}  Pacey={sp:.4f}  -> {'Block' if sb>sp else 'Pacey'}  margin={abs(sb-sp):.4f}")
    print()

print("="*70); print("Re-check real-data discrimination with the override table, lam=0.6")
pool = load_foundation_candidates("FC26", positions={"CM","CDM","CAM"})
def spearman(xs, ys):
    def rank(v):
        o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for p,i in enumerate(o): r[i]=p
        return r
    rx,ry=rank(xs),rank(ys); n=len(xs); mx=sum(rx)/n; my=sum(ry)/n
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))**0.5
    return num/den if den else 0.0
tops={}; rhos=[]
for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
    w = compose("CM", prof, 0.6, HIGH_POLE_OVERRIDE)
    sc=[(score(c,w),c) for c in pool]; sc=[(s,c) for s,c in sc if s is not None]
    sc.sort(key=lambda t:(-t[0],t[1].name))
    tops[prof]={c.name for _,c in sc[:10]}
    rhos.append(spearman([s for s,_ in sc],[c.overall_rating for _,c in sc]))
ov=[len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
print(f"mean_overlap={sum(ov)/len(ov):.1f}/10  PRESSING∩LOW_BLOCK={len(tops['PRESSING']&tops['LOW_BLOCK'])}/10  rho=[{min(rhos):.2f},{max(rhos):.2f}]")

# also re-verify the original session-1 adversarial pairs still pass with the OVERRIDE table
CB_pool_check = load_foundation_candidates("FC26", positions={"CB"})
print("\nCB position weights sanity check (top5):", sorted(cfg.position_attribute_weights("CB").items(), key=lambda kv:-kv[1])[:5])

print("\n" + "="*70)
print("Cross-position overlap sweep, override table")
for pos, poolpos in (("CM",{"CM","CDM","CAM"}), ("CB",{"CB","LB","RB"}), ("ST",{"ST","LW","RW"})):
    pool = load_foundation_candidates("FC26", positions=poolpos)
    for lam in (0.6, 0.7, 0.8):
        tops={}
        for prof in ("PRESSING","POSSESSION","LOW_BLOCK","PACE_ABUSER","DIRECT_PLAY"):
            w = compose(pos, prof, lam, HIGH_POLE_OVERRIDE)
            sc=[(score(c,w),c) for c in pool]; sc=[(s,c) for s,c in sc if s is not None]
            sc.sort(key=lambda t:(-t[0],t[1].name))
            tops[prof]={c.name for _,c in sc[:10]}
        ov=[len(tops[a]&tops[b]) for a,b in itertools.combinations(tops,2)]
        pl=len(tops["PRESSING"]&tops["LOW_BLOCK"])
        print(f"  {pos:3s} lam={lam:.1f}  mean_overlap={sum(ov)/len(ov):4.1f}/10  PRESS∩LOWBLOCK={pl}/10")

# re-confirm the ORIGINAL 6 adversarial cases from session 1 still pass with the override table + capability-only scoring
print("\n" + "="*70); print("Re-run session-1's original 6 adversarial cases with the v3 signed composition")
def A(**kw): return make_attrs(**kw)
CASES=[]
CASES.append(("LOW_BLOCK RM: 87 attacker vs 82 worker","RM","LOW_BLOCK",
  [("Attacker87",87,A(pace=90,dribbling_detail=90,finishing=85,crossing=84,defending=40,
                      interceptions=38,standing_tackle=35,stamina=70,acceleration=88,
                      curve=80,short_passing=72,long_passing=68,agility=86,balance=80,
                      defensive_awareness=40)),
   ("Worker82",82,A(pace=78,dribbling_detail=75,finishing=70,crossing=76,defending=75,
                    interceptions=74,standing_tackle=72,stamina=88,acceleration=76,
                    curve=70,short_passing=76,long_passing=72,agility=74,balance=76,
                    defensive_awareness=76))],"Worker82"))
press=A(stamina=92,aggression=86,interceptions=85,defensive_awareness=83,short_passing=78,
        vision=74,long_passing=72,ball_control=76,composure=74,positioning=78,strength=82,
        standing_tackle=84,reactions=82,acceleration=78,pace=76,long_shots=68,
        dribbling_detail=72,curve=66,agility=74,balance=76)
poss=A(stamina=72,aggression=60,interceptions=62,defensive_awareness=68,short_passing=90,
       vision=92,long_passing=88,ball_control=90,composure=89,positioning=80,strength=68,
       standing_tackle=60,reactions=84,acceleration=74,pace=70,long_shots=80,
       dribbling_detail=86,curve=84,agility=84,balance=82)
CASES.append(("PRESSING CM: press vs poss (both 84)","CM","PRESSING",[("Press",84,press),("Poss",84,poss)],"Press"))
CASES.append(("POSSESSION CM: press vs poss (both 84)","CM","POSSESSION",[("Press",84,press),("Poss",84,poss)],"Poss"))
CASES.append(("GUARD POSSESSION CM: identical shape, 80 vs 88","CM","POSSESSION",
  [("Lower80",80,A(**{k:max(1,v-8) for k,v in poss.values.items()})),("Higher88",88,poss)],"Higher88"))
weakshape=A(**{k:max(1,int(v*0.62)) for k,v in poss.values.items()})
CASES.append(("GUARD POSSESSION CM: perfect shape@62% vs solid 84","CM","POSSESSION",
  [("PerfectShapeWeak",58,weakshape),("SolidPoss84",84,poss)],"SolidPoss84"))
for lam in (0.6,):
    print(f"--- lambda={lam} ---")
    for title,pos,prof,cands,expect in CASES:
        w = compose(pos, prof, lam, HIGH_POLE_OVERRIDE)
        rows=[]
        for nm,ovr,at in cands:
            c=make_candidate(name=nm,position=pos,ovr=ovr,attrs=at)
            rows.append((score(c,w),nm))
        rows.sort(key=lambda r:-r[0])
        ok = rows[0][1]==expect
        print(f"  [{'PASS' if ok else 'FAIL'}] {title[:52]:52s} -> {rows[0][1]:16s} margin={abs(rows[0][0]-rows[1][0]):.4f}")
