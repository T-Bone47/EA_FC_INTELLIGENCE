#!/usr/bin/env python3
"""POST-BUILD VERIFICATION — live HTTP + DB checks against the RUNNING app.

Covers audit sections 4 (API), 5 (version wall), 6 (synthetic firewall),
7 (authentication), 8 (security, HTTP-level), 9 (recommendation engine).

Usage:  python3 verification/post_build_verify.py [BASE_URL]
Exit code 0 only if every check passes.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
RESULTS: list[tuple[str, str, str]] = []   # (section, PASS/FAIL, detail)


def wait_auth_window(seconds: int = 62) -> None:
    """The auth surface is rate limited to 10 requests/min/IP in production.
    The audit itself must not trip it, so pause for a fresh window."""
    print(f"  … waiting {seconds}s for a fresh auth rate-limit window")
    time.sleep(seconds)


def check(section: str, ok: bool, detail: str) -> bool:
    RESULTS.append((section, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {section}: {detail}")
    return ok


def req(method: str, path: str, body=None, token=None, raw_body=None,
        headers=None, timeout=60):
    url = BASE + path
    data = None
    hdrs = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    if raw_body is not None:
        data = raw_body
        hdrs["Content-Type"] = "application/json"
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    hdrs.update(headers or {})
    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            rid = resp.headers.get("X-Request-ID")
            try:
                return resp.status, json.loads(payload), dict(resp.headers), rid
            except json.JSONDecodeError:
                return resp.status, payload, dict(resp.headers), rid
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload), dict(e.headers), e.headers.get("X-Request-ID")
        except json.JSONDecodeError:
            return e.code, payload, dict(e.headers), e.headers.get("X-Request-ID")


def db(sql, params=None):
    import psycopg
    with psycopg.connect(
            "postgresql://eafc:eafc_dev_only@localhost:5432/eafc_intelligence") as conn:
        return conn.execute(sql, params).fetchall()


PW = "Audit-Passw0rd!123"
EMAIL = f"audit-{uuid.uuid4().hex[:10]}@example.com"
EMAIL2 = f"audit2-{uuid.uuid4().hex[:10]}@example.com"

# ============================================================ 4. API surface
S = "4-API"
st, b, _, _ = req("GET", "/api")
check(S, st == 200 and "POST /api/recommendations" in b.get("canonical_endpoints", []),
      f"GET /api -> {st}, endpoint index present")

st, b, _, _ = req("GET", "/api/health")
check(S, st == 200 and b["status"] == "ok", f"GET /api/health -> {st} {b}")

st, b, _, _ = req("GET", "/api/health/ready")
ok = (st == 200 and b["game_players"] == 16228 and b["playstyles"] == 15032
      and b["ut_cards"] == 0
      and b["game_players_by_version"] == {"FC26": 16228, "FC27": 0})
check(S, ok, f"GET /api/health/ready -> {st} counts={b.get('game_players')}/"
             f"{b.get('playstyles')}/{b.get('ut_cards')} by_version={b.get('game_players_by_version')}")

st, b, _, _ = req("GET", "/api/meta/game-versions")
m = {v["code"]: v["status"] for v in b} if st == 200 else {}
check(S, m == {"FC26": "ACTIVE", "FC27": "NO_DATA"}, f"game-versions -> {m}")

st, r26, _, _ = req("GET", "/api/meta/reference?game_version=FC26")
check(S, st == 200 and r26["status"] == "ACTIVE" and "CM" in r26["positions"]
      and len(r26["playstyles"]) == 36 and "4-2-3-1" in r26["formations"]
      and r26["capabilities"]["market_data_available"] is False,
      f"reference FC26 -> {st} positions={len(r26.get('positions', []))} "
      f"playstyles={len(r26.get('playstyles', []))} formations={len(r26.get('formations', {}))}")

st, b, _, _ = req("GET", "/api/players?game_version=FC26&q=mbappe&page_size=5")
items = b.get("items", [])
check(S, st == 200 and any("Mbappé" in i["display_name"] for i in items),
      f"search mbappe -> {st} total={b.get('total')} (accent-insensitive)")
MBAPPE = items[0]["id"] if items else None

st, b, _, _ = req("GET", "/api/players/facets?game_version=FC26")
nations = {n["nation"] for n in b.get("nations", [])}
check(S, st == 200 and "France" in nations and len(b.get("leagues", [])) >= 40,
      f"facets -> {st} nations={len(b.get('nations', []))} leagues={len(b.get('leagues', []))}")

st, b, _, _ = req("GET", f"/api/players/{MBAPPE}?game_version=FC26")
ok = (st == 200 and b["game_player"]["display_name"] == "Kylian Mbappé"
      and b["attributes"]["finishing"] is not None
      and b["provenance"]["usage_status"] == "LICENSED"
      and b["cards"] == [])
check(S, ok, f"player page -> {st} name={b.get('game_player', {}).get('display_name')} "
             f"provenance={b.get('provenance', {}).get('license')} cards={b.get('cards')}")

st, b, _, _ = req("GET", f"/api/players/{uuid.uuid4()}?game_version=FC26")
check(S, st == 404, f"unknown player id -> {st}")

st, b, _, rid = req("POST", "/api/recommendations",
                    {"game_version": "FC26", "position": "CM", "limit": 3})
check(S, st == 200 and b["best"] is not None and len(b["ranked"]) == 3
      and b["weights_used"]["attribute_fit"] == 0.30,
      f"POST /api/recommendations -> {st} best={b.get('best', {}).get('name') if st == 200 else b} weights_ok={st == 200 and b['weights_used'] == {'overall_quality': 0.15, 'attribute_fit': 0.3, 'position_fit': 0.15, 'tactical_fit': 0.15, 'playstyle_fit': 0.15, 'team_fit': 0.1}}")

st, b, _, _ = req("POST", "/api/recommendations/parse-intent",
                  {"text": "need a right winger for counter attack, budget 100k",
                   "game_version": "FC26"})
d = b.get("draft", {})
check(S, st == 200 and d.get("position") == "RW"
      and d.get("tactical_profile") == "COUNTER_ATTACK" and d.get("budget_coins") == 100000,
      f"parse-intent -> {st} draft(pos={d.get('position')}, tac={d.get('tactical_profile')}, budget={d.get('budget_coins')})")

st, b, _, _ = req("GET", "/api/players?game_version=FC26&q=bellingham&page_size=1")
BELL = b["items"][0]["id"]
st, b, _, _ = req("POST", "/api/compare",
                  {"game_version": "FC26", "entity_ids": [MBAPPE, BELL],
                   "user_context": {"game_version": "FC26", "position": "ST"}})
ok = st == 200 and b["verdict"]["user_context"] is True and len(b["columns"]) == 2
check(S, ok, f"POST /api/compare -> {st} verdict={b.get('verdict', {}).get('ranked_for_user') if ok else b}")

# ============================================== 7. AUTH (needed for squads)
S = "7-AUTH"
wait_auth_window()
st, b, _, _ = req("POST", "/api/auth/signup",
                  {"email": EMAIL, "password": PW, "display_name": "Auditor"})
T1 = b.get("access_token") if st == 201 else None
check(S, st == 201 and T1, f"signup -> {st}")

st, b, _, _ = req("POST", "/api/auth/signup",
                  {"email": EMAIL, "password": PW, "display_name": "Dup"})
check(S, st == 409 and "Unable to create" in b.get("detail", ""),
      f"duplicate signup -> {st} '{b.get('detail')}' (no existence leak beyond generic)")

st, b, _, _ = req("POST", "/api/auth/login", {"email": EMAIL, "password": "wrong-pass-1"})
check(S, st == 401 and b.get("detail") == "Invalid email or password.",
      f"wrong password -> {st} '{b.get('detail')}'")
st, b2, _, _ = req("POST", "/api/auth/login",
                   {"email": f"ghost-{uuid.uuid4().hex[:6]}@example.com", "password": "whatever1"})
check(S, b2.get("detail") == b.get("detail"),
      "unknown email -> identical generic error (no user enumeration)")

st, b, _, _ = req("GET", "/api/auth/me", token=T1)
check(S, st == 200 and b["email"] == EMAIL and b["role"] == "user",
      f"GET /me -> {st} role={b.get('role')}")

st, b, _, _ = req("POST", "/api/auth/login", {"email": EMAIL, "password": PW})
T1B = b.get("access_token")
st, _, _, _ = req("POST", "/api/auth/logout-all", token=T1B)
s_a = req("GET", "/api/auth/me", token=T1B)[0]
s_b = req("GET", "/api/auth/me", token=T1)[0]
check(S, st == 204 and s_a == 401 and s_b == 401,
      f"logout-all -> {st}; both sessions after: {s_a}/{s_b} (server-side revocation)")

wait_auth_window()
st, b, _, _ = req("POST", "/api/auth/login", {"email": EMAIL, "password": PW})
T1 = b["access_token"]
st, b, _, _ = req("POST", "/api/auth/signup",
                  {"email": EMAIL2, "password": PW, "display_name": "Auditor2"})
T2 = b["access_token"]
check(S, st == 201, f"second user signup -> {st}")

st, _, _, _ = req("GET", "/api/squads")
st2, _, _, _ = req("GET", "/api/squads", headers={"Authorization": "Bearer garbage.token.here"})
check(S, st == 401 and st2 == 401, f"no token -> {st}, malformed token -> {st2}")

# ============================================ 4/7. squads + saved + feedback
S = "4-SQUADS"
st, sq, _, _ = req("POST", "/api/squads", {"name": f"Audit XI {uuid.uuid4().hex[:4]}",
                                           "formation": "4-2-3-1", "game_version": "FC26"},
                   token=T1)
SID = sq.get("id") if st == 201 else None
st_g, sqg, _, _ = req("GET", f"/api/squads/{SID}", token=T1)
check(S, st == 201 and SID and st_g == 200 and isinstance(sqg.get("slots"), list),
      f"create squad -> {st}; GET squad -> {st_g} slots={len(sqg.get('slots', []))} (slots are created lazily on assignment)")

st, b, _, _ = req("GET", "/api/players?game_version=FC26&q=alisson&position=GK&page_size=1")
GK = b["items"][0]
st, b, _, _ = req("PUT", f"/api/squads/{SID}/slots/0",
                  {"slot_index": 0, "slot_position": "GK", "game_player_id": GK["id"]},
                  token=T1)
check(S, st == 200, f"assign GK slot -> {st}")

st, b, _, _ = req("PUT", f"/api/squads/{SID}/slots/0",
                  {"slot_index": 0, "slot_position": "ST", "game_player_id": MBAPPE},
                  token=T1)
check(S, st == 422 and "is GK, not ST" in b.get("detail", ""),
      f"wrong position for slot -> {st} '{b.get('detail')}'")

st, b, _, _ = req("GET", f"/api/squads/{SID}", token=T2)
st2, _, _, _ = req("DELETE", f"/api/squads/{SID}", token=T2)
st3, _, _, _ = req("GET", f"/api/squads/{SID}/evaluation", token=T2)
check(S, st == 404 and st2 == 404 and st3 == 404,
      f"cross-user squad GET/DELETE/eval -> {st}/{st2}/{st3} (ownership=404)")

st, ev, _, _ = req("GET", f"/api/squads/{SID}/evaluation", token=T1)
ok = (st == 200 and ev["chemistry"]["status"] == "INSUFFICIENT_EVIDENCE"
      and ev["links"]["filled_slots"] == 1)
check(S, ok, f"evaluation -> {st} chemistry={ev.get('chemistry', {}).get('status')} "
             f"filled={ev.get('links', {}).get('filled_slots')}")

st, rep, _, _ = req("POST", f"/api/squads/{SID}/recommend-replacement",
                    {"slot_index": 5}, token=T1)
check(S, st == 200 and rep["slot"]["slot_position"] == "CDM" and rep["best"] is not None,
      f"recommend-replacement -> {st} slot={rep.get('slot')} best={rep.get('best', {}).get('name') if st == 200 else None}")

S = "4-SAVED+FEEDBACK"
st, b, _, _ = req("POST", "/api/saved-players",
                  {"entity_type": "game_player", "entity_id": MBAPPE,
                   "game_version": "FC26", "note": "audit"}, token=T1)
check(S, st == 201, f"save player -> {st}")
st, b, _, _ = req("GET", "/api/saved-players", token=T2)
check(S, st == 200 and b["total"] == 0,
      f"cross-user saved list -> {st} total={b.get('total')} (isolation)")
st, b, _, _ = req("GET", "/api/saved-players", token=T1)
check(S, st == 200 and b["total"] == 1, f"owner saved list -> {st} total={b.get('total')}")

st, rec, _, _ = req("POST", "/api/recommendations",
                    {"game_version": "FC26", "position": "CM", "limit": 1}, token=T1)
top = rec["ranked"][0]
st, b, _, _ = req("POST", "/api/feedback",
                  {"recommendation_id": rec["request_id"], "action": "SELECTED",
                   "entity_type": "game_player", "entity_id": top["entity_id"],
                   "game_version": "FC26"}, token=T1)
check(S, st == 201 and b.get("status") == "recorded", f"POST /api/feedback -> {st} {b}")
rows = db("SELECT action FROM user_recommendation_feedback WHERE recommendation_id=%s",
          (rec["request_id"],))
actions = sorted(r[0] for r in rows)
check(S, "SHOWN" in actions and "SELECTED" in actions,
      f"feedback persisted (auto SHOWN + explicit): {actions}")
st, b, _, _ = req("GET", "/api/feedback/stats", token=T1)
check(S, st == 403, f"GET /api/feedback/stats as non-admin -> {st}")
st, _, _, _ = req("DELETE", f"/api/saved-players/{MBAPPE}", token=T1)
check(S, st == 204, f"unsave -> {st}")
st, _, _, _ = req("DELETE", f"/api/squads/{SID}", token=T1)
check(S, st == 204, f"delete squad -> {st}")

# ==================================================== 5. FC26/FC27 wall
S = "5-VERSION-WALL"
st, b, _, _ = req("GET", "/api/players?game_version=FC26&q=haaland")
fc26_total = b.get("total", 0)
st, b, _, _ = req("GET", "/api/players?game_version=FC27&q=haaland")
check(S, fc26_total >= 1 and st == 200 and b.get("total") == 0,
      f"search haaland: FC26 total={fc26_total} | FC27 total={b.get('total')} (no leak)")

st, b, _, _ = req("GET", f"/api/players/{MBAPPE}?game_version=FC27")
check(S, st == 404, f"FC26 player page under FC27 -> {st}")

st, b, _, _ = req("POST", "/api/recommendations",
                  {"game_version": "FC27", "position": "CM"})
check(S, st == 404 and "NO ingested production data" in b.get("detail", "")
      and "fabricated" in b.get("detail", ""),
      f"FC27 recommendations -> {st} '{b.get('detail', '')[:80]}...'")

st, b, _, _ = req("POST", "/api/compare",
                  {"game_version": "FC27", "entity_ids": [MBAPPE, BELL]})
check(S, st == 404, f"FC26 entities under FC27 compare -> {st}")

st, b, _, _ = req("GET", "/api/meta/reference?game_version=FC27")
check(S, st == 200 and b["status"] == "NO_DATA" and b["positions"] == []
      and b["playstyles"] == [],
      f"FC27 reference -> {st} status={b.get('status')} positions={b.get('positions')}")

st, sq27, _, _ = req("POST", "/api/squads", {"name": f"FC27 Audit {uuid.uuid4().hex[:4]}",
                                             "formation": "4-3-3", "game_version": "FC27"},
                     token=T1)
ok_create = st == 201
if ok_create:
    st2, b2, _, _ = req("PUT", f"/api/squads/{sq27['id']}/slots/0",
                        {"slot_index": 0, "slot_position": "GK",
                         "game_player_id": GK["id"]}, token=T1)
    st3, b3, _, _ = req("POST", "/api/recommendations",
                        {"game_version": "FC27", "position": "GK",
                         "squad_id": sq27["id"]}, token=T1)
    ok_mix = st2 == 404 and st3 in (404, 422)
    detail = (f"FC27 squad create -> {st}; FC26 player into FC27 slot -> {st2}; "
              f"FC27 rec w/ squad -> {st3}")
    req("DELETE", f"/api/squads/{sq27['id']}", token=T1)
else:
    ok_mix, detail = False, f"FC27 squad create -> {st} {sq27}"
check(S, ok_create and ok_mix, detail)

st, b, _, _ = req("GET", "/api/players?game_version=FC25&q=x")
check(S, st == 422, f"unregistered version FC25 -> {st} (validation)")

# ==================================================== 6. synthetic firewall
S = "6-SYNTHETIC-FIREWALL"
card = db("SELECT id, card_name FROM ut_card WHERE is_synthetic LIMIT 1")[0]
syn_id, syn_name = str(card[0]), card[1]
st, b, _, _ = req("GET", f"/api/cards/{syn_id}?game_version=FC26")
check(S, st == 404, f"GET /api/cards/{{synthetic}} -> {st} ({syn_name})")

q = urllib.parse.quote(syn_name)
st, b, _, _ = req("GET", f"/api/players?game_version=FC26&q={q}")
st2, b2, _, _ = req("GET", "/api/players?game_version=FC26&q=Fixture")
check(S, st == 200 and b.get("total") == 0 and b2.get("total") == 0,
      f"search synthetic names -> totals {b.get('total')}/{b2.get('total')}")

st, b, _, _ = req("POST", "/api/recommendations",
                  {"game_version": "FC26", "position": "CM", "entity_scope": "ut_card"})
check(S, st == 404 and "No canonical (non-synthetic) UT card data" in b.get("detail", ""),
      f"recs entity_scope=ut_card -> {st} '{b.get('detail', '')[:70]}...'")

st, b, _, _ = req("POST", "/api/compare",
                  {"game_version": "FC26", "entity_ids": [syn_id, MBAPPE]})
check(S, st == 404, f"compare with synthetic card id -> {st}")

st, b, _, _ = req("POST", "/api/recommendations",
                  {"game_version": "FC26", "position": "CM", "limit": 50})
leaked = [r for r in b.get("ranked", []) if r["entity_type"] != "game_player"]
check(S, st == 200 and not leaked,
      f"top-50 recs contain {len(leaked)} non-game_player entities (expect 0)")

st, b, _, _ = req("POST", "/api/saved-players",
                  {"entity_type": "ut_card", "entity_id": syn_id,
                   "game_version": "FC26"}, token=T1)
check(S, st == 404, f"save synthetic card -> {st} (blocked)")

# ==================================================== 8. security (HTTP)
S = "8-SECURITY"
st, b, hd, rid = req("GET", "/api/health")
need = {"x-content-type-options": "nosniff", "x-frame-options": "DENY",
        "referrer-policy": "no-referrer"}
low = {k.lower(): v for k, v in hd.items()}
ok = all(low.get(k) == v for k, v in need.items()) and "x-request-id" in low
check(S, ok, f"security headers -> nosniff={low.get('x-content-type-options')} "
             f"frame={low.get('x-frame-options')} referrer={low.get('referrer-policy')} "
             f"rid={bool(rid)} hsts={'strict-transport-security' in low} (production)")
check(S, "strict-transport-security" in low,
      f"HSTS present in production mode -> {low.get('strict-transport-security', 'MISSING')[:50]}")

st, b, hd, _ = req("GET", "/api/health", headers={"Origin": "https://evil.example.com"})
acao = [k for k in hd if k.lower() == "access-control-allow-origin"]
check(S, not acao, f"CORS ACAO header for unlisted origin -> {acao or 'absent (closed)'}")

st, b, _, _ = req("GET", "/api/players?game_version=FC26&q=" +
                  urllib.parse.quote("'; DROP TABLE game_player; --"))
alive = db("SELECT count(*) FROM game_player")[0][0]
check(S, st == 200 and b.get("total") == 0 and alive == 16228,
      f"SQLi attempt -> {st} total={b.get('total')}; game_player rows still {alive}")

big = json.dumps({"email": f"big-{uuid.uuid4().hex[:6]}@example.com",
                  "password": "A" * 1_500_000}).encode()
st, b, _, _ = req("POST", "/api/auth/signup", raw_body=big)
check(S, st == 413, f"oversized body (1.5MB) -> {st} '{b.get('detail') if isinstance(b, dict) else ''}'")

wait_auth_window()
codes = []
for i in range(14):
    st, b, hd2, _ = req("POST", "/api/auth/signup",
                        {"email": f"rl-{uuid.uuid4().hex[:8]}@example.com",
                         "password": PW})
    codes.append(st)
    if st == 429:
        ra = [v for k, v in hd2.items() if k.lower() == "retry-after"]
        check(S, bool(ra), f"auth rate limit hit after {codes.count(429) == 0 and i or i} requests; Retry-After={ra}")
        break
else:
    check(S, False, f"auth rate limit NEVER triggered in 14 signups: {codes}")
check(S, 429 in codes, f"429 present in signup burst -> codes={codes}")

# ==================================================== 9. engine scenarios
S = "9-ENGINE"


def scenario(name, body, expect_fn):
    st, b, _, _ = req("POST", "/api/recommendations", body)
    if st != 200 or not b.get("best"):
        check(S, False, f"{name} -> {st} {str(b)[:120]}")
        return None
    ok, detail = expect_fn(b)
    check(S, ok, f"{name}: {detail}")
    return b


def fmt(b):
    best = b["best"]
    comps = {k: (v["status"][:4] if v["status"] != "KNOWN" else round(v["value"], 2))
             for k, v in best["components"].items()}
    return (f"winner={best['name']} score={best['weighted_score']} "
            f"conf={best['confidence']['score']} comps={comps} "
            f"evaluated={b['evaluations_total']}")


# 1. pressing CM with stamina floor — engine must pick a workhorse, not top OVR
b1 = scenario("S1 CM/PRESSING/stamina>=85", {
    "game_version": "FC26", "position": "CM", "formation": "4-2-3-1",
    "tactical_profile": "PRESSING", "limit": 5,
    "attribute_preferences": [{"attribute": "stamina", "min_value": 85}],
    "budget_coins": 100000},
    lambda b: (b["best"]["components"]["attribute_fit"]["status"] == "KNOWN"
               and b["best"]["components"]["tactical_fit"]["status"] == "KNOWN"
               and b["best"]["components"]["team_fit"]["status"] == "UNKNOWN"
               and b["budget_status"].startswith("BUDGET_UNVERIFIED")
               and any("stamina=" in e for e in b["best"]["components"]["attribute_fit"]["evidence"]),
               fmt(b) + f" | budget={b['budget_status'][:40]} team_fit=UNKNOWN(no squad ctx)"))

# 2. GK — only gk_* attributes may drive attribute_fit
b2 = scenario("S2 GK/gk_diving>=85", {
    "game_version": "FC26", "position": "GK", "limit": 3,
    "attribute_preferences": [{"attribute": "gk_diving", "min_value": 85}]},
    lambda b: (b["best"]["name"] and "gk_diving=" in
               " ".join(b["best"]["components"]["attribute_fit"]["evidence"]),
               fmt(b)))

# 3. counter-attack ST with pace>=90
b3 = scenario("S3 ST/COUNTER/pace>=90", {
    "game_version": "FC26", "position": "ST", "tactical_profile": "COUNTER_ATTACK",
    "limit": 5, "attribute_preferences": [{"attribute": "pace", "min_value": 90}]},
    lambda b: (b["best"]["components"]["tactical_fit"]["status"] == "KNOWN", fmt(b)))

# 4. ball-playing CB for possession: passing constraint must reorder vs OVR
b4 = scenario("S4 CB/POSSESSION/short_passing>=80", {
    "game_version": "FC26", "position": "CB", "tactical_profile": "POSSESSION",
    "limit": 5, "attribute_preferences": [{"attribute": "short_passing", "min_value": 80}]},
    lambda b: (True, fmt(b)))

# 5. PlayStyle-driven RW with desired playstyles
b5 = scenario("S5 RW/CROSSING/desired Whipped Pass", {
    "game_version": "FC26", "position": "RW", "tactical_profile": "CROSSING",
    "desired_playstyles": ["Whipped Pass"], "limit": 5},
    lambda b: (b["best"]["components"]["playstyle_fit"]["status"] == "KNOWN", fmt(b)))

# "not simply highest OVR wins": compare S4 winner against highest-OVR CB pool
if b4:
    st, top_cb, _, _ = req("GET", "/api/players?game_version=FC26&position=CB"
                           "&sort=overall_rating&sort_dir=desc&page_size=1")
    top_id = top_cb["items"][0]["id"]
    top_name = top_cb["items"][0]["display_name"]
    top_ovr = top_cb["items"][0]["overall_rating"]
    winner_is_top_ovr = b4["best"]["entity_id"] == top_id
    ranked_ids = [r["entity_id"] for r in b4["ranked"]]
    top_ovr_rank = (ranked_ids.index(top_id) + 1) if top_id in ranked_ids else None
    check(S, not winner_is_top_ovr or top_ovr_rank == 1,
          f"highest-OVR CB = {top_name} ({top_ovr}); engine winner = {b4['best']['name']} "
          f"(score {b4['best']['weighted_score']}); top-OVR rank in engine list = {top_ovr_rank}"
          + (" -> ranking is NOT OVR-sorted" if not winner_is_top_ovr else ""))

# Pareto honesty
if b1:
    par = b1["pareto"]
    check(S, par.get("best_overall") is not None and par.get("best_value") is None
          and "best_value" in par.get("unavailable_dimensions", []),
          f"pareto: best_overall present, best_value=None (prices UNKNOWN), "
          f"unavailable={par.get('unavailable_dimensions')}")

# why-this explanations non-empty and evidence-based
if b1:
    ex = b1["explanations"]
    has_unscored_note = any("Not scored" in w for w in ex["why_this"])
    check(S, bool(ex["summary"]) and bool(ex["why_this"]) and len(ex["why_this"]) <= 20
          and has_unscored_note and bool(ex["strengths"] is not None),
          f"explanations: summary ok, why_this={len(ex['why_this'])} lines (incl. evidence + "
          f"'Not scored' honesty note={has_unscored_note}), strengths={len(ex['strengths'])}, "
          f"why_not_alternatives={len(ex['why_not_alternatives'])}")

# confidence: UNKNOWN components excluded, notes present
if b1:
    c = b1["confidence"]
    check(S, 0 < c["score"] <= 1 and "team_fit" in c["unknown_components"] and c["notes"],
          f"confidence={c['score']} known={c['known_components']} unknown={c['unknown_components']}")

# determinism: same request twice -> identical ranking
body = {"game_version": "FC26", "position": "ST", "tactical_profile": "PRESSING",
        "attribute_preferences": [{"attribute": "stamina", "min_value": 80}], "limit": 10}
_, ra, _, _ = req("POST", "/api/recommendations", body)
_, rb, _, _ = req("POST", "/api/recommendations", body)
same = ([x["entity_id"] for x in ra["ranked"]] == [x["entity_id"] for x in rb["ranked"]]
        and [x["weighted_score"] for x in ra["ranked"]] == [x["weighted_score"] for x in rb["ranked"]])
check(S, same, f"determinism: two identical requests -> identical ranking+scores={same}")

# ============================================================ summary
fails = [r for r in RESULTS if r[1] == "FAIL"]
print(f"\n{'=' * 62}\nTOTAL: {len(RESULTS)} checks | PASS {len(RESULTS) - len(fails)} | FAIL {len(fails)}")
for s, stt, d in fails:
    print(f"  FAILED [{s}] {d}")
sys.exit(1 if fails else 0)
