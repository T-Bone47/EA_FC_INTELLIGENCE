"""Phase 24 -- FC27 card identity layer (migration 009): quarantine, version wall, open flags.

Guard tests run on any database that has migration 009. Data tests only run when the
package was ingested (scripts/ingest_fc27_card_identity.py) and skip otherwise.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest

from backend.core.config import get_settings

RESEARCH_SRC = "futgg_fc27_identity_research"
TABLES = ("card_source_snapshot", "fc27_rarity_catalogue", "fc27_card_identity", "fc27_role_reference",
          "fc27_playstyle_page_reference", "fc27_card_open_flag")


@pytest.fixture()
def cur():
    with psycopg.connect(get_settings().database_url) as conn:
        c = conn.cursor()
        yield c
        conn.rollback()


def _gv(cur, code):
    cur.execute("select id from game_version where code=%s", (code,))
    return cur.fetchone()[0]


def _snapshot(cur):
    sid = f"test-snap-{uuid.uuid4().hex[:8]}"
    cur.execute("""insert into card_source_snapshot(snapshot_id,game_version_id,source_id,package_name,package_version,license_note,retrieved_at_semantics,audit_status)
                   values (%s,%s,%s,'t','t','t','t','t')""", (sid, _gv(cur, "FC27"), RESEARCH_SRC))
    return sid


def _try_rarity(cur, sid, *, gv="FC27", source=RESEARCH_SRC, status="RESEARCH_ONLY"):
    cur.execute("""insert into fc27_rarity_catalogue(game_version_id,futgg_rarity_id,ea_rarity_id,rarity_name,slug,card_count,is_pseudo_rarity,
                   source_id,snapshot_id,package_retrieved_at,acquired_from,acquired_to,data_status)
                   values (%s,999001,999001,'t','t',0,false,%s,%s,now(),now(),now(),%s)""", (_gv(cur, gv), source, sid, status))


def test_fixture_row_is_accepted_when_everything_is_correct(cur):
    _try_rarity(cur, _snapshot(cur))       # control: proves the negative tests fail for the intended reason


def test_database_rejects_fc26_rows(cur):
    sid = _snapshot(cur)
    with pytest.raises(psycopg.errors.CheckViolation, match="FC27"):
        _try_rarity(cur, sid, gv="FC26")


@pytest.mark.parametrize("status", ["CANONICAL", "PENDING_REVIEW", "SYNTHETIC_TEST"])
def test_database_rejects_any_status_but_research_only(cur, status):
    sid = _snapshot(cur)
    with pytest.raises(psycopg.errors.CheckViolation):
        _try_rarity(cur, sid, status=status)


@pytest.mark.parametrize("source", ["futgg", "kaggle_justdhia_ea_fc26_player_ratings", "no_such_source"])
def test_database_rejects_non_research_or_unregistered_sources(cur, source):
    sid = _snapshot(cur)
    with pytest.raises(psycopg.errors.CheckViolation):
        _try_rarity(cur, sid, source=source)


def test_registry_policy_not_silently_changed(cur):
    cur.execute("select usage_status, legal_gate from source_registry where source_id='futgg'")
    assert cur.fetchone() == ("NOT_PERMITTED", "REQUIRED")
    cur.execute("select usage_status, legal_gate from source_registry where source_id=%s", (RESEARCH_SRC,))
    assert cur.fetchone() == ("RESEARCH_ONLY", "REQUIRED"), "research source must stay RESEARCH_ONLY and NOT cleared"


def test_no_price_or_market_columns_exist(cur):
    cur.execute("""select table_name, column_name from information_schema.columns
                   where table_name = any(%s) and (column_name ilike '%%price%%' or column_name ilike '%%coin%%' or column_name ilike '%%market%%')""",
                (list(TABLES) + ["fc27_card_player_spine"],))
    assert cur.fetchall() == []


def test_no_production_module_reads_the_research_card_tables():
    root = Path(__file__).resolve().parents[1]
    needles = list(TABLES) + ["fc27_card_player_spine"]
    offenders = [str(p.relative_to(root)) for p in root.rglob("*.py")
                 if "tests" not in p.parts and any(n in p.read_text(encoding="utf-8") for n in needles)]
    assert offenders == [], offenders


def _ingested(cur):
    cur.execute("select count(*) from fc27_card_identity")
    if cur.fetchone()[0] == 0:
        pytest.skip("FC27 card package not ingested in this database")


def test_ingested_counts_match_the_audited_package(cur):
    _ingested(cur)
    cur.execute("select count(*), count(distinct source_card_id), count(distinct source_player_id), "
                "count(*) filter (where is_base_style), count(*) filter (where sitemap_row_count=2) from fc27_card_identity")
    assert cur.fetchone() == (20175, 20175, 19620, 18824, 14)
    cur.execute("select count(*), sum(card_count) from fc27_rarity_catalogue"); assert cur.fetchone() == (26, 20189)
    cur.execute("select count(*) from fc27_role_reference"); assert cur.fetchone()[0] == 114
    cur.execute("select count(*), sum(sitemap_row_count) from fc27_playstyle_page_reference"); assert cur.fetchone() == (41, 141)


def test_spine_view_matches_identity_and_keeps_player_card_distinct(cur):
    _ingested(cur)
    cur.execute("select count(*), sum(fc27_card_count) from fc27_card_player_spine"); assert cur.fetchone() == (19620, 20175)
    cur.execute("select count(*) from fc27_card_identity where source_card_id <> source_player_id and is_base_style"); assert cur.fetchone()[0] == 0


def test_player_join_uses_fc27_game_player_only(cur):
    _ingested(cur)
    cur.execute("""select count(*) from fc27_card_identity i join game_player gp on gp.id=i.game_player_id join game_version v on v.id=gp.game_version_id
                   where v.code <> 'FC27' or gp.source_player_id::text <> i.source_player_id""")
    assert cur.fetchone()[0] == 0
    cur.execute("select count(distinct source_player_id) from fc27_card_identity where game_player_id is not null"); assert cur.fetchone()[0] == 19357


def test_no_card_id_is_ever_joined_across_versions(cur):
    _ingested(cur)
    cur.execute("select count(*) from fc27_card_identity i join ut_card u on u.source_card_id = i.source_card_id"); assert cur.fetchone()[0] == 0


def test_open_flags_are_preserved_and_none_resolved(cur):
    _ingested(cur)
    cur.execute("select flag_type, count(*) from fc27_card_open_flag where status='OPEN' group by 1"); open_ = dict(cur.fetchall())
    assert open_["DUPLICATE_SITEMAP_ROW"] == 14 and open_["PACKAGE_CONFLICT"] == 3 and open_["STRUCTURAL_QUESTION"] == 1
    cur.execute("select count(*) from fc27_card_open_flag where status='RESOLVED'"); assert cur.fetchone()[0] == 0
    cur.execute("select count(*) from fc27_card_open_flag where flag_type='PACKAGE_CONFLICT' and entity='fc27_card_universe_size' and status='OPEN'"); assert cur.fetchone()[0] == 1
