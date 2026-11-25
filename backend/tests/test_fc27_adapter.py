"""Phase 22 -- EA-ratings CSV adapter, snapshot validator, pipeline status.

All rows here are SYNTHETIC TEST FIXTURES written to tmp_path (names start
with "Fixture"). They exercise parsing and fail-closed rules only; they are
never evidence about real FC27 data (see test_fc27_real_data.py for that).
"""
from __future__ import annotations

import csv
import uuid
from pathlib import Path

import pytest

from backend.domain.card_model import DataStatus, GamePlayer
from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.ingestion.adapter import LegalGateError
from backend.ingestion.data_quality import DataQualityValidator
from backend.ingestion.ea_ratings_csv_adapter import (
    ATTRIBUTE_COLUMN_MAP,
    EXPECTED_COLUMNS,
    EARatingsCsvAdapter,
    SourceSchemaMismatch,
    parse_playstyles,
)
from backend.ingestion.fc27_research_profile import (
    FC27_RESEARCH_VERSION_CONFIG,
    POSITION_VOCABULARY,
)
from backend.ingestion.normalizer import Normalizer
from backend.ingestion.pipeline import IngestionPipeline
from backend.ingestion.snapshot_validation import validate_snapshot
from backend.services.scoring_config import ScoringConfig


def _row(pid: int, position: str = "CM", **over) -> dict:
    r = {c: "" for c in EXPECTED_COLUMNS}
    r.update({"player_id": str(pid), "first_name": "Fixture", "last_name": f"Player{pid}",
              "overall_rating": "80", "position": position, "club": "Fixture FC",
              "league": "Fixture League", "nationality": "Fixtureland",
              "gender": "Men's Football", "preferred_foot": "Right", "skill_moves": "3",
              "weak_foot": "3", "birthdate": "2000-01-01", "edition": "fc27",
              "snapshot_date": "2026-09-12"})
    for i, c in enumerate(list(ATTRIBUTE_COLUMN_MAP) + ["pace", "shooting", "passing",
                                                         "dribbling", "defending",
                                                         "physicality"]):
        r[c] = str(40 + (i % 50))
    r.update(over)
    return r


def _write(path: Path, rows: list[dict], header=EXPECTED_COLUMNS) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(header), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def _source(usage=UsageStatus.RESEARCH_ONLY, gate="CLEARED") -> SourceRecord:
    return SourceRecord(source_id="fixture_research_source", name="fixture",
                        source_type="CARRIER_DATASET", authority_tier=4,
                        usage_status=usage, legal_gate=gate)


class _MemoryRepo:
    def __init__(self):
        self.players: list[GamePlayer] = []

    def upsert_game_player(self, gp, base, plus, published):
        self.players.append(gp)

    def upsert_card(self, card, payload):
        raise AssertionError("no cards expected")


# ---------------------------------------------------------------- schema
class TestSchemaFailClosed:
    def test_exact_header_is_accepted(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1)])
        assert len(EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()) == 1

    def test_extra_column_stops_the_run(self, tmp_path):
        header = list(EXPECTED_COLUMNS) + ["new_attribute"]
        p = _write(tmp_path / "p.csv", [dict(_row(1), new_attribute="50")], header)
        with pytest.raises(SourceSchemaMismatch, match="new_attribute"):
            EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()

    def test_missing_column_stops_the_run(self, tmp_path):
        header = [c for c in EXPECTED_COLUMNS if c != "skill_curve"]
        p = _write(tmp_path / "p.csv", [_row(1)], header)
        with pytest.raises(SourceSchemaMismatch, match="skill_curve"):
            EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()

    def test_one_foreign_edition_row_refuses_whole_file(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1), _row(2, edition="fc26")])
        with pytest.raises(ValueError, match="contamination"):
            EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()

    def test_legal_gate_still_applies(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1)])
        with pytest.raises(LegalGateError):
            EARatingsCsvAdapter(_source(gate="REQUIRED"), "FC27", p).fetch_players()


# ---------------------------------------------------------------- mapping
class TestColumnMapping:
    def test_prefixed_detail_columns_land_on_canonical_names(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1, attacking_short_passing="77",
                                             skill_dribbling="66",
                                             mentality_positioning="55",
                                             goalkeeping_positioning="12",
                                             defending_awareness="44")])
        a = EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()[0].attributes
        assert a["short_passing"] == "77"
        assert a["dribbling_detail"] == "66"
        assert a["positioning"] == "55"          # attacking positioning
        assert a["gk_positioning"] == "12"       # goalkeeping positioning, separate
        assert a["defensive_awareness"] == "44"
        assert not any(k.startswith(("attacking_", "skill_", "movement_", "power_",
                                     "mentality_", "defending_", "goalkeeping_"))
                       for k in a)

    def test_outfield_face_stats_map_to_facades(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1, pace="91")])
        a = EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()[0].attributes
        assert a["pace"] == "91"

    def test_goalkeeper_face_stats_are_not_mapped_to_outfield_facades(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1, position="GK", pace="87",
                                             goalkeeping_diving="87")])
        rec = EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()[0]
        for facade in ("pace", "shooting", "passing", "dribbling", "defending", "physicality"):
            assert facade not in rec.attributes
        assert rec.extras["unmapped_source_values"]["pace"] == "87"
        gp = Normalizer("fixture_research_source", "FC27").normalize_player(rec)
        assert gp.attributes.get("pace") is None          # UNKNOWN, not 87
        assert gp.attributes.get("gk_diving") == 87

    def test_space_separated_alternates_become_positions(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1, alternate_positions="CAM  ST")])
        rec = EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()[0]
        gp = Normalizer("fixture_research_source", "FC27").normalize_player(rec)
        assert gp.secondary_positions == ["CAM", "ST"]

    def test_invalid_foot_becomes_unknown_and_is_reported(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1, preferred_foot="Both")])
        ad = EARatingsCsvAdapter(_source(), "FC27", p)
        rec = ad.fetch_players()[0]
        assert rec.extras["preferred_foot"] is None
        assert "preferred_foot" in ad.field_issues["1"][0]

    def test_height_weight_blank_stay_unknown(self, tmp_path):
        p = _write(tmp_path / "p.csv", [_row(1)])
        rec = EARatingsCsvAdapter(_source(), "FC27", p).fetch_players()[0]
        gp = Normalizer("fixture_research_source", "FC27").normalize_player(rec)
        assert gp.height_cm is None and gp.weight_kg is None


# ---------------------------------------------------------------- playstyles
class TestPlayStyleParsing:
    def test_trailing_plus_is_playstyle_plus(self):
        assert parse_playstyles("Finesse Shot, Tiki Taka, Incisive Pass+") == (
            ["Finesse Shot", "Tiki Taka"], ["Incisive Pass"], [])

    def test_source_wording_is_preserved(self):
        base, plus, _ = parse_playstyles("Some New FC27 Style")
        assert base == ["Some New FC27 Style"] and plus == []

    @pytest.mark.parametrize("raw,fragment", [
        ("Rapid, , Technical", "empty"),
        ("Rapid++", "malformed"),
        ("Rapid, Rapid", "duplicate"),
        ("Rapid, Rapid+", "duplicate"),
        ("Ra+pid", "inside"),
    ])
    def test_malformed_tokens_are_reported_not_repaired(self, raw, fragment):
        _, _, issues = parse_playstyles(raw)
        assert issues and any(fragment in i for i in issues)

    def test_empty_cell_means_no_published_list(self):
        assert parse_playstyles("") == ([], [], [])


# ---------------------------------------------------------------- pipeline
class TestPipelineDataStatus:
    def _run(self, tmp_path, usage):
        p = _write(tmp_path / "p.csv", [_row(1, playstyles="Rapid, Technical+"), _row(2)])
        repo = _MemoryRepo()
        pipe = IngestionPipeline(
            EARatingsCsvAdapter(_source(usage=usage), "FC27", p), repo,
            validator=DataQualityValidator(ScoringConfig.with_versions([FC27_RESEARCH_VERSION_CONFIG])))
        return pipe.run_players(), repo

    def test_research_only_source_yields_research_only_rows(self, tmp_path):
        report, repo = self._run(tmp_path, UsageStatus.RESEARCH_ONLY)
        assert report.players_persisted == 2 and report.players_rejected == 0
        assert {gp.data_status for gp in repo.players} == {DataStatus.RESEARCH_ONLY}

    def test_playstyle_published_flag_and_tiers(self, tmp_path):
        _, repo = self._run(tmp_path, UsageStatus.RESEARCH_ONLY)
        by_id = {gp.source_player_id: gp for gp in repo.players}
        assert by_id[1].playstyle_data_published is True
        assert by_id[1].playstyles_base == ["Rapid"] and by_id[1].playstyles_plus == ["Technical"]
        assert by_id[2].playstyle_data_published is False   # UNKNOWN, not "none"


# ---------------------------------------------------------------- identity
class TestVersionScopedIdentity:
    def test_same_ea_id_different_versions_is_different_game_player(self):
        a = Normalizer("src", "FC26").game_player_id(123)
        b = Normalizer("src", "FC27").game_player_id(123)
        assert a != b

    def test_same_ea_id_same_version_is_stable(self):
        assert Normalizer("src", "FC27").game_player_id(123) == \
            Normalizer("src", "FC27").game_player_id(123)


# ---------------------------------------------------------------- snapshot validator
class TestSnapshotValidation:
    def _validate(self, rows, expected=None):
        header = list(EXPECTED_COLUMNS)
        norm = Normalizer("fixture_research_source", "FC27")
        return validate_snapshot(header, rows, expected_edition="fc27",
                                 expected_row_count=expected,
                                 position_vocabulary=set(POSITION_VOCABULARY),
                                 reference_playstyle_vocabulary={"Rapid"},
                                 canonical_id_fn=norm.game_player_id)

    def test_clean_rows_pass(self):
        rep = self._validate([_row(1), _row(2)], expected=2)
        assert rep["verdict"] == "PASS"
        assert rep["row_outcomes"] == {"accepted": 2, "flagged": 0, "rejected": 0}

    def test_every_rejection_carries_a_reason(self):
        rows = [_row(1), _row(1), _row(3, overall_rating=""), _row(4, position="LWB"),
                _row(5, attacking_crossing="104"), _row(6, alternate_positions="CM XX")]
        rep = self._validate(rows)
        rejected = {r["row_index"] for r in rep["rejected_rows"]}
        assert rejected == {0, 1, 2, 3, 4, 5}
        assert all(r["reasons"] for r in rep["rejected_rows"])
        assert rep["identity"]["duplicate_source_player_ids"] == ["1"]

    def test_row_count_mismatch_is_blocking(self):
        rep = self._validate([_row(1)], expected=2)
        assert rep["verdict"] == "FAIL"
        assert any("row count" in b for b in rep["blocking_reasons"])

    def test_new_playstyle_names_are_reported_not_mapped(self):
        rep = self._validate([_row(1, playstyles="Rapid, Brand New Style")])
        assert rep["playstyles"]["names_not_in_reference_vocabulary"] == ["Brand New Style"]
        assert rep["row_outcomes"]["rejected"] == 0

    def test_playstyle_plus_not_last_is_flagged(self):
        rep = self._validate([_row(1, playstyles="Rapid+, Technical")])
        assert rep["row_outcomes"]["flagged"] == 1

    def test_canonical_ids_include_version(self):
        rep = self._validate([_row(1)])
        assert "GAME_VERSION" in rep["identity"]["canonical_id_rule"]
        assert isinstance(Normalizer("s", "FC27").game_player_id(1), uuid.UUID)
