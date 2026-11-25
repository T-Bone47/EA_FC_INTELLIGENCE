import sys, csv, json, hashlib, collections; sys.path.insert(0,'.')
from backend.data_access.foundation_loader import load_foundation_candidates
from backend.domain.card_model import DETAIL_ATTRS, FACADE_ATTRS, GK_ATTRS

# ---------- PHASE 11: coverage census ----------
rows=list(csv.DictReader(open('data/fc26_real_foundation/players.csv',encoding='utf-8-sig')))
ps=list(csv.DictReader(open('data/fc26_real_foundation/player_playstyles.csv',encoding='utf-8-sig')))
ps_players={r['player_id'] for r in ps}
ps_plus={r['player_id'] for r in ps if r['tier']=='plus'}
gk={r['player_id'] for r in rows if r['position_primary']=='GK'}
def has_all(r,cols): return all(r.get(c) not in (None,'') for c in cols)
detail_ok=sum(1 for r in rows if r['player_id'] not in gk and has_all(r,DETAIL_ATTRS))
gk_ok=sum(1 for r in rows if r['player_id'] in gk and has_all(r,GK_ATTRS))
print("PHASE 11 — census of what actually exists in the repository")
print(f"  TOTAL_UNIQUE_GAME_PLAYERS (FC26)        {len(rows):,}")
print(f"  TOTAL_UNIQUE_PLAYERS (real_player rows) {sum(1 for _ in open('data/real_player_identities.csv'))-1}")
print(f"  TOTAL_UNIQUE_UT_CARDS (real)            0   <-- none")
print(f"  TOTAL_UT_CARDS (synthetic fixtures)     63  (SYNTHETIC_TEST only)")
print(f"  players WITH_OVR                        {sum(1 for r in rows if r['overall_rating']):,}")
print(f"  outfield WITH full DETAIL attributes    {detail_ok:,} / {len(rows)-len(gk):,}")
print(f"  GK WITH full GK attributes              {gk_ok:,} / {len(gk):,}")
print(f"  players WITH any PlayStyle              {len(ps_players):,}  ({len(ps_players)/len(rows)*100:.1f}%)")
print(f"  players WITH PlayStyle+                 {len(ps_plus):,}  ({len(ps_plus)/len(rows)*100:.2f}%)")
print(f"  players WITH Roles                      0   <-- no role data anywhere")
print(f"  players/cards WITH PRICES               0   <-- no market data anywhere")
print(f"  WITH_VERIFIED_EXTERNAL_PLAYER_ID        {sum(1 for r in rows if r['player_id']):,} (EA ratings item id)")
print(f"  WITH_VERIFIED_CARD_ID                   0")
print(f"  alternate_positions populated           {sum(1 for r in rows if r['alternate_positions']):,}")

# ---------- PHASE 13: frozen reference distributions ----------
POSGROUPS={"GK":{"GK"},"DEF":{"CB","LB","RB"},"MID":{"CDM","CM","CAM","LM","RM"},"ATT":{"LW","RW","ST"}}
def qtl(v,p):
    v=sorted(v); 
    if not v: return None
    f=p*(len(v)-1); lo=int(f); hi=min(lo+1,len(v)-1); r=f-lo
    return round(v[lo]*(1-r)+v[hi]*r,2)
print("\nPHASE 13 — frozen reference distribution feasibility (P10/P90 per position group)")
print(f"{'group':5s} {'n':>6s} {'attrs_with_n>=50':>17s} {'min_n_per_attr':>15s}   example: short_passing P10/P50/P90")
ref={}
for g,poss in POSGROUPS.items():
    sub=[r for r in rows if r['position_primary'] in poss]
    attrs = GK_ATTRS if g=="GK" else DETAIL_ATTRS
    ok=0; minn=10**9; ex=None
    ref[g]={}
    for a in attrs:
        vals=[float(r[a]) for r in sub if r.get(a) not in (None,'')]
        if len(vals)>=50:
            ok+=1; minn=min(minn,len(vals))
            ref[g][a]={"n":len(vals),"p10":qtl(vals,.10),"p50":qtl(vals,.50),"p90":qtl(vals,.90)}
        if a=='short_passing': ex=(qtl(vals,.10),qtl(vals,.50),qtl(vals,.90)) if vals else None
    print(f"{g:5s} {len(sub):6d} {ok:>13d}/{len(attrs):<3d} {minn if minn<10**9 else 0:>15d}   {ex}")
blob=json.dumps(ref,sort_keys=True).encode()
print(f"\n  reference_distribution content sha256 = {hashlib.sha256(blob).hexdigest()}")
print(f"  attributes covered: GK={len(ref['GK'])} DEF={len(ref['DEF'])} MID={len(ref['MID'])} ATT={len(ref['ATT'])}")
# float artifact check
from backend.services.scoring_config import ScoringConfig
cfg=ScoringConfig(); w=cfg.position_attribute_weights("CM")
print(f"\n  normalisation residual check: sum(position_attribute_weights['CM']) = {sum(w.values()):.17f}")
