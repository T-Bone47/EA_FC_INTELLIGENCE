"""Pipeline integration (in-memory repository): the documented synthetic card
fixture (63 rows) must yield 60 persisted + 3 rejected, legal gate enforced,
ids idempotent, version contamination blocked."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.ingestion.adapter import LegalGateError
from backend.ingestion.local_file_adapter import LocalFileAdapter
from backend.ingestion.pipeline import IngestionPipeline

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "data" / "fixtures" / "fictional_ut_cards.csv"
FOUNDATION = ROOT / "data" / "fc26_real_foundation"


class MemoryRepo:
    def __init__(self):
        self.players = {}
        self.cards = {}

    def upsert_game_player(self, gp, base, plus, published):
        self.players[gp.id] = gp

    def upsert_card(self, card, version_payload):
        self.cards[card.id] = (card, version_payload)


def synth_source(gate="NOT_REQUIRED"):
    return SourceRecord(source_id="synthetic_fixtures", name="synthetic",
                        source_type="SYNTHETIC_FIXTURE", authority_tier=5,
                        usage_status=UsageStatus.SYNTHETIC_TEST, legal_gate=gate)


def licensed_source(gate="CLEARED"):
    return SourceRecord(source_id="kaggle_justdhia_ea_fc26_player_ratings",
                        name="carrier", source_type="CARRIER_DATASET",
                        authority_tier=3, usage_status=UsageStatus.LICENSED,
                        legal_gate=gate)


def test_cards_60_valid_3_rejected():
    adapter = LocalFileAdapter(synth_source(), "FC26", cards_path=CARDS)
    repo = MemoryRepo()
    report = IngestionPipeline(adapter, repo).run_cards()
    assert report.cards_fetched == 63
    assert report.cards_persisted == 60
    assert report.cards_rejected == 3
    names = {r["name"] for r in report.rejections}
    assert names == {"Broken Rating Case", "Missing Rating Case", "Too Many Plus Case"}
    # every persisted card is firewalled as synthetic
    assert all(c.is_synthetic for c, _ in repo.cards.values())


def test_card_ids_idempotent_across_runs():
    def run():
        adapter = LocalFileAdapter(synth_source(), "FC26", cards_path=CARDS)
        repo = MemoryRepo()
        IngestionPipeline(adapter, repo).run_cards()
        return set(repo.cards)
    assert run() == run()


def test_legal_gate_blocks_uncleared_source():
    blocked = LocalFileAdapter(synth_source(gate="REQUIRED"), "FC26", cards_path=CARDS)
    with pytest.raises(LegalGateError):
        blocked.fetch_cards()


def test_legal_gate_blocks_production_source_without_clearance():
    adapter = LocalFileAdapter(licensed_source(gate="REQUIRED"), "FC26",
                               players_path=FOUNDATION / "players.csv")
    with pytest.raises(LegalGateError):
        adapter.fetch_players()


def test_foundation_ingestion_counts_match_forensics():
    adapter = LocalFileAdapter(
        licensed_source(), "FC26",
        players_path=FOUNDATION / "players.csv",
        playstyles_path=FOUNDATION / "player_playstyles.csv")
    repo = MemoryRepo()
    report = IngestionPipeline(adapter, repo).run_players(attach_playstyles=True)
    assert report.players_fetched == 16228
    assert report.players_persisted == 16228
    assert report.players_rejected == 0
    assert report.playstyles_attached == 15032
    gks = [gp for gp in repo.players.values() if gp.position_primary == "GK"]
    assert len(gks) == 1816
    # GK canonical shape: outfield facades UNKNOWN, GK attrs KNOWN (forensics F1/F2)
    gk = next(g for g in gks if g.attributes.get("gk_diving") is not None)
    assert gk.attributes.get("pace") is None
    assert gk.attributes.get("gk_reflexes") is not None
    outfield = next(gp for gp in repo.players.values() if gp.position_primary == "ST")
    assert outfield.attributes.get("finishing") is not None


def test_mixed_version_rows_rejected(tmp_path):
    # a foundation-style CSV containing an FC27 row must be refused wholesale
    src = FOUNDATION / "players.csv"
    lines = src.read_text().splitlines()
    bad = tmp_path / "players.csv"
    bad.write_text(lines[0] + "\n" + lines[1].replace("FC26", "FC27") + "\n")
    adapter = LocalFileAdapter(licensed_source(), "FC26", players_path=bad)
    with pytest.raises(ValueError, match="contamination"):
        adapter.fetch_players()
