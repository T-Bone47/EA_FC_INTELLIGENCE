from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.main import create_app
from backend.core import db
from backend.core.config import get_settings
from backend.services.performance_cohort import COHORT_DIGEST, load_cohort
from backend.services.performance_evidence import EvidenceIn, canonical_citation, compare_observed, opinion_summary, reported_matches

PATH = "/api/research/fc27/performance"
OPT = {"include_research_data": True}
CONTEXT = {"game_patch":"1.2.0","formation":"4-3-3","slot":"ST","position":"ST","role":"advanced forward",
           "tactical_profile":"HIGH_PRESS","game_mode":"friendly","controller":"HUMAN"}
ITEMS = ["231747", "239085"]


def sample(item, session, order, goals):
    return {"game_version":"FC27", "card_item_id":item, "source_key":"controlled", "evidence_locator":"private sheet row",
            "observation_type":"CONTROLLED_EXPERIMENT","rights_attested":True,"share_for_research":True,
            "context":CONTEXT, "match":{"match_date":"2026-11-10","match_key":f"{item}-{session}","minutes":90,
                "platform":"PC","opponent_context":"professional AI","skill_context":"operator A","setup_key":"setup-a",
                "protocol_key":"review-pilot","session_key":session,"block_key":"block-1","order":order,
                "metrics":{"goals":goals,"passes_completed":None}}}


def as_row(item, session, order, goals):
    payload = sample(item, session, order, goals)
    return {"id": str(uuid4()), "card_item_id":item,"owner_id":"same-reporter",
            "evidence_kind":"CONTROLLED_EXPERIMENT","payload":payload}


def test_pairing_is_patch_specific_counterbalanced_and_does_not_impute():
    rows = [as_row("a","s1",1,2),as_row("b","s1",2,0),as_row("a","s2",2,1),as_row("b","s2",1,0)]
    result = compare_observed(rows,["a","b"],"goals",CONTEXT)
    assert result["observed_per_90"] == {"a":1.5,"b":0.0}
    assert result == compare_observed(reversed(rows),["a","b"],"goals",CONTEXT)
    assert compare_observed(rows,["a","b"],"goals",{**CONTEXT,"game_patch":"1.3.0"})["observed_per_90"] is None
    assert compare_observed(rows,["a","b"],"passes_completed",CONTEXT)["observed_per_90"] is None
    assert compare_observed(rows[:2],["a","b"],"goals",CONTEXT)["observed_per_90"] is None
    different = deepcopy(rows)
    for row in different[2:]:
        row["payload"]["match"]["setup_key"] = "different"
    assert compare_observed(different,["a","b"],"goals",CONTEXT)["observed_per_90"] is None
    dispute = deepcopy(rows[0])
    dispute["payload"]["match"]["metrics"]["goals"] = 8
    assert len(reported_matches([*rows,dispute])[1]) == 1
    assert compare_observed([*rows,dispute],["a","b"],"goals",CONTEXT)["observed_per_90"] is None


def test_citation_dedup_and_independent_disagreement():
    assert canonical_citation("https://youtu.be/abcdefghijk?si=123") == canonical_citation(
        "https://www.youtube.com/watch?v=abcdefghijk&utm_source=copy")
    def opinion(source, stance, note):
        return {"id":str(uuid4()),"card_item_id":"a","evidence_kind":"COMMUNITY_OPINION","source_key":source,
                "payload":{"source_url":"https://example.org/claim","context":CONTEXT,"topic":"turning","stance":stance,"note":note}}
    rows = [opinion("futgg","SUPPORTS","turns early"),opinion("fctactics","SUPPORTS","turns early!"),
            opinion("ea-forums","CONTRADICTS","late turning")]
    result = opinion_summary(rows)[0]
    assert (result["status"],result["supporting_origins"],result["contradicting_origins"]) == ("CONFLICTING",1,1)
    with pytest.raises(ValidationError):
        item = sample(str(uuid4()),"s1",1,2)
        item["match"]["metrics"]["shots_on_target"] = 1
        EvidenceIn.model_validate(item)


def test_live_frozen_cohort_and_postgresql_review():
    settings = get_settings()
    if not settings.fc27_card_research_enabled or not db.query_one("SELECT to_regclass('fc27_staging.performance_evidence') AS t")["t"]:
        pytest.skip("Run with the local FC27 release and migration 014")
    manifest, cohort = load_cohort(settings.database_url)
    assert manifest["cohort_digest"] == COHORT_DIGEST
    assert len(cohort) == len({item["card_item_id"] for item in cohort}) == 136
    assert all(item["rarity"]=="Rare" and not item["identity_conflict"] for item in cohort)
    assert all(count==3 for count in manifest["control_positions"].values())
    assert [item["source_item_id"] for item in cohort[:3]] == ["227203", *ITEMS]
    cards = [next(item["card_item_id"] for item in cohort if item["source_item_id"]==source) for source in ITEMS]
    owners = []
    with TestClient(create_app(),base_url="http://127.0.0.1",client=("127.0.0.1",61211)) as client:
        def account(admin=False):
            login = {"email":f"phase31-{uuid4().hex}@example.com","password":"Phase31-local-test!"}
            result = client.post("/api/auth/signup",json=login)
            assert result.status_code==201, result.text
            user_id = result.json()["user"]["id"]
            owners.append(user_id)
            if admin:
                db.execute("UPDATE user_profile SET role='admin' WHERE id=%s",(user_id,))
                result = client.post("/api/auth/login",json=login)
            assert "access_token" in result.json(), result.text
            return {"Authorization":"Bearer "+result.json()["access_token"]}

        try:
            reporter, reviewer = account(), account(admin=True)
            assert client.get(PATH).status_code == 422
            full = client.get(PATH+"?include_research_data=true")
            assert full.status_code == 200 and full.headers["cache-control"] == "private, no-store", full.text
            assert client.get(PATH+"?include_research_data=true",headers={"x-forwarded-host":"local"}).status_code==403
            assert client.get(PATH+"/review?include_research_data=true",headers=reporter).status_code==403
            selected = {**OPT,"game_version":"FC27","card_ids":cards,"metric":"goals","context":CONTEXT}
            clean = client.post(PATH+"/compare",json=selected)
            assert clean.status_code==200, clean.text
            baseline = clean.json()["predictions"]
            assert len(baseline)==2 and clean.json()["observed"]["observed_per_90"] is None
            assert client.post(PATH+"/compare",json={**selected,"game_version":"FC26"}).status_code==422
            special = next(row["entity_id"] for row in client.get("/api/research/fc27/cards",
                params={"include_research_data":"true","q":"50563395"}).json()["items"] if row["source_item_id"]=="50563395")
            assert client.post(PATH+"/compare",json={**selected,"card_ids":[special,cards[1]]}).status_code==404
            records = [sample(cards[0],"s1",1,2),sample(cards[1],"s1",2,0),
                       sample(cards[0],"s2",2,1),sample(cards[1],"s2",1,0)]
            batch = {**OPT,"records":records}
            assert client.post(PATH+"/submissions",json=batch).status_code==401
            inserted = client.post(PATH+"/submissions",json=batch,headers=reporter)
            assert inserted.status_code==201, inserted.text
            ids = inserted.json()["ids"]
            assert client.post(PATH+"/submissions",json=batch,headers=reporter).json()["ids"]==ids
            conflict = deepcopy(records[0]); conflict["match"]["metrics"]["goals"]=5
            assert client.post(PATH+"/submissions",json={**OPT,"records":[sample(cards[0],"s3",1,0),conflict]},
                               headers=reporter).status_code==409
            assert len(client.get(PATH+"/submissions?include_research_data=true",headers=reporter).json()["items"])==4
            assert client.get(PATH+"/submissions?include_research_data=true",headers=reviewer).json()["items"]==[]
            assert client.get(PATH+f"/items/{cards[0]}?include_research_data=true").json()["reviewed_evidence"]==[]
            decision = {**OPT,"decision":"ACCEPTED","reason":"Validated test evidence and permission."}
            for record in ids:
                result = client.post(PATH+"/review/"+record,json=decision,headers=reviewer)
                assert result.status_code==200, result.text
            compared = client.post(PATH+"/compare",json=selected).json()
            assert compared["predictions"]==baseline
            assert compared["observed"]["observed_per_90"]=={cards[0]:1.5,cards[1]:0.0}
            assert client.post(PATH+"/compare",json={**selected,"context":{**CONTEXT,"role":"poacher"}}).json()["observed"]["observed_per_90"] is None
            detail = client.get(PATH+f"/items/{cards[0]}?include_research_data=true&patch=1.3.0").json()
            assert detail["compatible_match_count"]==0
            assert all(row["patch_compatibility"]=="OTHER_PATCH" and "payload" not in row for row in detail["reviewed_evidence"])
            withdraw = {**OPT,"decision":"WITHDRAWN","reason":"Remove study fixture"}
            assert client.post(PATH+"/review/"+ids[0],json=withdraw,headers=reviewer).status_code==404
            assert client.post(PATH+"/review/"+ids[0],json=withdraw,headers=reporter).status_code==200
            assert client.post(PATH+"/compare",json=selected).json()["observed"]["observed_per_90"] is None
        finally:
            for owner in owners:
                db.execute("DELETE FROM user_profile WHERE id=%s",(owner,))
