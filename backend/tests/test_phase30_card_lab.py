import itertools
import random
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.routes.card_squad_lab import router
from backend.api.routes.research_cards import research_service
from backend.core import db
from backend.core.config import get_settings
from backend.services.card_squad_lab import identity_group, nondominated
from backend.services.fc27_card_research import RELEASE, SNAPSHOT
from backend.services.formation_optimizer import assignment_frontier, optimal_assignments
from backend.tests.conftest import requires_db

ROOT = "/api/research/fc27/cards"
SCOPE = dict(game_version="FC27",entity_scope="ut_card",release_id=RELEASE,include_research_data=True)


def test_grouped_assignment_exhaustive():
    rng = random.Random(3001)
    for _ in range(3000):
        n = rng.randint(1, 4)
        identities = {str(i):str(rng.randrange(4)) for i in range(rng.randint(1,6))}
        rows = [[dict(entity_id=i,identity_group=g,score=rng.randrange(5)/10)
                 for i,g in identities.items() if rng.random() < .6] for _ in range(n)]
        current = [rng.choice([None,*identities]) for _ in rows]
        best, frontier = None, {}
        for path in itertools.product(*[[None,*r] for r in rows]):
            items = [r for r in path if r]
            if len({r["identity_group"] for r in items}) != len(items):
                continue
            ids = tuple(r["entity_id"] if r else "" for r in path)
            edits = sum(bool(i) and i!=old for i,old in zip(ids,current))
            rank = (-len(items),-sum(round(r["score"]*10) for r in items),edits,ids)
            if best is None or rank<best:
                best = rank
            if edits not in frontier or rank<frontier[edits]:
                frontier[edits]=rank
        def ids(rows):
            return tuple(r["entity_id"] if r else "" for r in rows)
        assert ids(optimal_assignments(rows,current)) == best[-1]
        assert {k:ids(v) for k,v in assignment_frontier(rows,current,count_changes=True).items()} == {
            k:v[-1] for k,v in frontier.items()}
        assert ids(optimal_assignments([r[::-1] for r in rows],current)) == best[-1]


def test_two_new_items_can_require_joint_release_of_two_footballer_groups():
    def row(item, identity, score):
        return dict(entity_id=item, identity_group=identity, score=score)
    options=[[row("old-a","A",.4),row("new-b","B",.6)],
             [row("old-b","B",.5),row("new-a","A",.7)]]
    paths=assignment_frontier(options,["old-a","old-b"],count_changes=True)
    assert any(r is None for r in paths[1])
    assert [r["entity_id"] for r in paths[2]]==["new-b","new-a"]


def test_pareto_and_identity_semantics():
    from types import SimpleNamespace
    vectors = list(itertools.product(range(3),repeat=2))
    for subset in itertools.chain(itertools.combinations(vectors,2),itertools.combinations(vectors,4)):
        expected = {i for i,(x,y) in enumerate(subset) if not any(
            (u>x and v>=y) or (u>=x and v>y) for u,v in subset)}
        assert set(nondominated(subset))==expected
    def card(item,status):
        return SimpleNamespace(entity_id=item,name="Same",extra={"identity_status":status,"confirmed_base_id":"42"})
    assert identity_group(card("1","RESOLVED")) == identity_group(card("2","RESOLVED"))
    assert identity_group(card("1","PROVISIONAL")) != identity_group(card("2","AMBIGUOUS"))


@pytest.fixture
def lab():
    if not db.query_one("select to_regclass('fc27_staging.card_squad') as table_name")["table_name"]:
        pytest.skip("Phase 30 migration absent")
    if not db.query_one("select 1 from fc27_staging.snapshot where snapshot_id=%s",(SNAPSHOT,)):
        pytest.skip("Private release absent")
    from unittest.mock import patch
    cfg=get_settings().model_copy(update={"fc27_card_research_enabled":True,"environment":"test"})
    with patch("backend.api.routes.research_cards.get_settings",return_value=cfg), TestClient(
        create_app(),base_url="http://127.0.0.1",client=("127.0.0.1",53002)) as client:
        yield client


@requires_db
def test_live_lab_ownership_locks_feedback_and_upgrade(lab):
    def items(q):
        reply=lab.get(ROOT,params={"q":q,"include_research_data":"true"})
        assert reply.status_code==200,reply.text
        return reply.json()["items"]
    yam=items("Yamal")
    keeper=next(i for i in items("Courtois") if i["positions"][0]=="GK" and i["base_identity_status"]!="CONFLICTED")
    versions=[c["entity_id"] for c in yam]
    kid=keeper["entity_id"]
    plan={**SCOPE,"formation":"4-3-3","candidate_ids":[kid,*versions],"assigned":{"GK":kid},"locked_slots":["GK"],
          "alternatives":["HIGH_PRESS","POSSESSION"]}
    def preview(p):
        return lab.post(ROOT+"/squad/preview",json=p)
    r=preview(plan)
    assert r.status_code==200,r.text
    result=r.json()
    assert result["optimized"]["slots"][0]["status"]=="LOCKED_UNSCORED"
    assert result["optimized"]["slots"][0]["score"] is None and result["optimized"]["scored"] > 0
    assert not result["optimized"]["footballer_uniqueness_verified"]
    assert result["price"] is result["chemistry"] is None
    assert preview({**plan,"confirmed_only":True}).status_code==422
    strict=preview({**plan,"confirmed_only":True,"assigned":{},"locked_slots":[]}).json()
    assert strict["admissible_items"]==0 and strict["optimized"]["scored"]==0
    assert preview({**plan,"candidate_ids":[kid,*versions,kid]}).status_code==422
    assert preview({**plan,"assigned":{"GK":versions[0]}}).status_code==422
    assert preview({**plan,"locked_slots":[]}).status_code==422
    assert preview({**plan,"excluded":[kid]}).status_code==422
    assert preview({**plan,"candidate_ids":[kid,str(uuid.uuid4())]}).status_code==422
    assert preview({**plan,"release_id":"other"}).status_code==422
    moved=lab.post(ROOT+"/squad/transform",json={"plan":{**plan,"assigned":{"GK":kid,"RW":versions[0]}},
                                                "target":"4-4-2"}).json()
    assert moved["assignments"]=={"GK":kid,"RM":versions[0]}
    invalid=lab.post(ROOT+"/squad/transform",json={"plan":{**plan,"assigned":{"GK":kid,"RW":versions[0]},
                                                "locked_slots":["RW","GK"]},"target":"4-4-2"})
    assert invalid.status_code==422
    pair={"request":{"game_version":"FC27","position":"RW","include_research_data":True,
                     "formation":"4-3-3","slot":"RW"},"card_ids":versions}
    scores=lab.post(ROOT+"/compare",json=pair).json()["players"]
    weak=scores[-1]["entity_id"]
    for mode in ("one","minimum","two"):
        p={**plan,"assigned":{"GK":kid,"RW":weak},"upgrade":mode}
        upgrades=preview(p).json()
        if mode=="two":
            assert upgrades["upgrade_status"]=="NO_IMPROVING_SOLUTION"
        else:
            assert upgrades["upgrade_gain"]>0 and len(upgrades["upgrades"])==1
            assert upgrades["upgrades"][0]["before_score"]==scores[-1]["score"]
    multi=lab.post(ROOT+"/compare-tactics",json={**pair,"profiles":["HIGH_PRESS","POSSESSION"]}).json()
    from unittest.mock import patch
    from backend.services import card_squad_lab as domain
    real_score=domain.score_slots
    def drop_alternate_lock(service,body,slots,profile):
        scored=real_score(service,body,slots,profile)
        if profile=="HIGH_PRESS":
            scored["RW"].pop(weak,None)
        return scored
    with patch.object(domain,"score_slots",side_effect=drop_alternate_lock):
        guarded=preview({**plan,"assigned":{"RW":weak},"locked_slots":["RW"]}).json()
        assert guarded["unavailable_profiles"]["HIGH_PRESS"]["slots"]==["RW"]
        assert "HIGH_PRESS" not in [m["optimized_for"] for m in guarded["matrix"]]
    assert multi["tested_profiles"]==2
    assert {"RM","RW"} == set(multi["position_fits"])
    assert all(set(row)==set(versions) for row in multi["position_fits"].values())
    assert lab.post(ROOT+"/squad/preview",json=plan,headers={"Forwarded":"for=192.0.2.1"}).status_code==403
    assert all(set(x["scores"])==set(versions) for x in multi["outcomes"])
    def login():
        uid=str(uuid.uuid4())
        response=lab.post("/api/auth/signup",json={"email":uid+"@example.com","password":"Phase30-"+uid,"display_name":"QA"})
        assert response.status_code==201,response.text
        return {"Authorization":"Bearer "+response.json()["access_token"]}
    owner,other=login(),login()
    save={ "plan":plan, "receipt":result["receipt"], "name":"Phase 30 test"}
    path=ROOT+"/squad/saved"
    assert lab.post(path,json=save).status_code==401
    assert lab.post(path,json={**save,"receipt":"0"*64},headers=owner).status_code==409
    def save_copy(_):
        response=lab.post(path,json=save,headers=owner)
        assert response.status_code==201,response.text
        return response.json()["id"]
    with ThreadPoolExecutor(2) as ex:
        saved=list(ex.map(save_copy,range(2)))
    assert saved[0]==saved[1]
    get=path+"/"+saved[0]+"?include_research_data=true"
    assert lab.get(get,headers=other).status_code==404
    assert lab.get(get,headers=owner).json()["preview"]["receipt"]==result["receipt"]
    recommended=lab.post(ROOT+"/recommendations",json=pair["request"],headers=owner).json()
    post={"include_research_data":True,"card_item_id":recommended["ranked"][0]["entity_id"],
          "recommendation_id":recommended["request_id"],"receipt":recommended["feedback_receipt"],"action":"SELECTED"}
    for _ in range(2):
        f=lab.post(ROOT+"/feedback",json=post,headers=owner)
        assert f.status_code==200,f.text
    assert lab.post(ROOT+"/feedback",json=post,headers=other).status_code==422
    assert lab.post(ROOT+"/feedback",json={**post,"action":"REJECTED"},headers=owner).status_code==409
    assert lab.post(ROOT+"/feedback",json={**post,"card_item_id":kid},headers=owner).status_code==422


@requires_db
def test_append_conflict_fails_closed_and_transaction_rolls_back(lab):
    from unittest.mock import patch
    from backend.services import fc27_card_research as release
    with db.get_conn() as conn:
        with pytest.raises(RuntimeError, match="roll back"):
            with conn.transaction():
                conn.execute("""INSERT INTO fc27_staging.observation(snapshot_id,record_id,source_row_number,raw,normalized)
                                VALUES(%s,'phase30-transaction-probe',999999999,'{}','{}')""",(SNAPSHOT,))
                with patch.object(release.db,"query_one",side_effect=lambda sql,params:conn.execute(sql,params).fetchone()):
                    with pytest.raises(ValueError,match="membership changed"):
                        release.validate_cached_membership()
                raise RuntimeError("roll back")
    release.validate_cached_membership()
    with patch("backend.api.routes.research_cards.validate_cached_membership",side_effect=ValueError("changed")):
        response=lab.post(ROOT+"/squad/preview",json={**SCOPE,"formation":"4-3-3","candidate_ids":[]})
        assert response.status_code==503


def test_every_lab_route_requires_local_release():
    for route in router.routes:
        assert research_service in [d.call for d in route.dependant.dependencies]
