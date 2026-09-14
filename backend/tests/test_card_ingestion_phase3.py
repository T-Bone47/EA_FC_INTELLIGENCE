"""Phase 3 §18/§19/§23/§26/§27 — meta-signal firewall, forensics, run tracking."""
from __future__ import annotations

import uuid

import pytest

from backend.domain.evidence_model import SourceRecord, UsageStatus
from backend.ingestion import meta_signals as ms
from backend.ingestion.forensics import analyze_rows
from backend.tests.conftest import requires_db


def _src(status=UsageStatus.SYNTHETIC_TEST, gate="NOT_REQUIRED", sid="meta_test_src"):
    return SourceRecord(source_id=sid, name="meta test", source_type="OTHER",
                        authority_tier=4, usage_status=status, legal_gate=gate)


# ------------------------------------------------------------------ §23 forensics
class TestForensics:
    def test_clean_dataset_passes(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        rows = [{"source_card_id": f"c{i}", "game_version": "FC26",
                 "overall_rating": 80 + (i % 10), "position": "ST",
                 "pace": 80, "playstyles": "Rapid", "playstyles_plus": "",
                 "observed_at": now}
                for i in range(10)]
        stats = analyze_rows(rows, entity="card", game_version="FC26",
                             id_column="source_card_id",
                             known_playstyles={"Rapid"})
        assert stats["verdict"] == "PASS"
        assert stats["duplicate_rate"] == 0.0

    def test_duplicates_and_bad_ratings_reject(self):
        rows = [{"source_card_id": "dup", "overall_rating": 120},
                {"source_card_id": "dup", "overall_rating": 80},
                {"source_card_id": "", "overall_rating": 80}]
        stats = analyze_rows(rows, entity="card", game_version="FC26",
                             id_column="source_card_id")
        codes = {f["code"] for f in stats["findings"]}
        assert "duplicate_identity" in codes
        assert "impossible_ratings" in codes
        assert "missing_identity" in codes
        assert stats["verdict"] == "REJECT"

    def test_version_contamination_rejects(self):
        rows = [{"source_card_id": "a", "game_version": "FC26"},
                {"source_card_id": "b", "game_version": "FC27"}]
        stats = analyze_rows(rows, entity="card", game_version="FC26",
                             id_column="source_card_id")
        assert any(f["code"] == "version_contamination" for f in stats["findings"])

    def test_unknown_playstyles_reject(self):
        rows = [{"source_card_id": "a", "playstyles": "NotARealPlayStyle",
                 "playstyles_plus": ""}]
        stats = analyze_rows(rows, entity="card", game_version="FC26",
                             id_column="source_card_id",
                             known_playstyles={"Rapid"})
        assert any(f["code"] == "unknown_playstyle" for f in stats["findings"])

    def test_multi_plus_flags_review(self):
        rows = [{"source_card_id": "a", "playstyles": "Rapid",
                 "playstyles_plus": "Rapid,Finesse Shot"}]
        stats = analyze_rows(rows, entity="card", game_version="FC26",
                             id_column="source_card_id",
                             known_playstyles={"Rapid", "Finesse Shot"})
        assert any(f["code"] == "playstyle_plus_cap" for f in stats["findings"])
        assert stats["verdict"] == "REVIEW"


# ------------------------------------------------------------------ §18/§19 meta firewall
class TestMetaSignals:
    def test_validation_rejects_bad_signals(self):
        with pytest.raises(ms.MetaSignalRejected):
            ms.validate_signal({"signal_type": "made_up", "entity_type": "ut_card"})
        with pytest.raises(ms.MetaSignalRejected):
            ms.validate_signal({"signal_type": "community_favorite",
                                "entity_type": "squad"})
        with pytest.raises(ms.MetaSignalRejected):
            ms.validate_signal({"signal_type": "community_favorite",
                                "entity_type": "ut_card", "sample_size": 0})

    def test_gated_source_cannot_store(self):
        src = _src(status=UsageStatus.UNKNOWN, gate="REQUIRED")
        with pytest.raises(ms.MetaSignalRejected, match="legal_gate"):
            ms.store_meta_signals(src, "FC26", [])

    @requires_db
    def test_store_and_read_back_labelled_as_perception(self):
        from backend.core.db import execute, query
        sid = f"meta_test_{uuid.uuid4().hex[:8]}"
        execute("""INSERT INTO source_registry (source_id, name, source_type,
                     authority_tier, usage_status, legal_gate, canonical_fields)
                   VALUES (%s,'meta test','OTHER',4,'SYNTHETIC_TEST',
                           'NOT_REQUIRED','{}')""", (sid,))
        try:
            src = _src(sid=sid)
            eid = uuid.uuid4()
            out = ms.store_meta_signals(src, "FC26", [
                {"signal_type": "community_favorite", "entity_type": "ut_card",
                 "entity_id": str(eid), "signal_strength": 0.8,
                 "sample_size": 1500, "payload": {"note": "test"}},
                {"signal_type": "bogus", "entity_type": "ut_card"},
            ])
            assert out["stored"] == 1 and out["rejected"] == 1
            assert out["data_status"] == "RESEARCH_ONLY"
            rows = ms.signals_for("ut_card", eid)
            assert len(rows) == 1
            assert rows[0]["kind"] == "META_SIGNAL"
            assert rows[0]["is_canonical"] is False
            # rejected row landed in quarantine, not silently dropped
            q = query("""SELECT count(*) n FROM ingestion_quarantine
                         WHERE source_id=%s AND entity_kind='meta_signal'""",
                      (sid,))[0]["n"]
            assert q == 1
            # FIREWALL: nothing written to canonical tables
            canon = query("SELECT count(*) n FROM ut_card WHERE id=%s", (eid,))[0]["n"]
            assert canon == 0
            assert ms.meta_watermark("FC26").startswith("meta:")
        finally:
            execute("DELETE FROM meta_signal WHERE source_id=%s", (sid,))
            execute("DELETE FROM ingestion_quarantine WHERE source_id=%s", (sid,))
            execute("DELETE FROM source_registry WHERE source_id=%s", (sid,))


# ------------------------------------------------------------------ §26/§27 run tracking
class TestRunTracker:
    @requires_db
    def test_run_lifecycle_and_failure(self):
        from backend.core.db import execute, query
        from backend.ingestion.run_tracker import IngestionRunTracker
        t = IngestionRunTracker("synthetic_fixtures", "FC26",
                                dataset_version="test-1")
        run_id = t.start(rows_raw=10)
        t.advance("STAGING")
        t.quarantine("card", "test reason", {"source_card_id": "x"}, "x")
        t.finish({"counts": {"players": 0, "cards": 9}, "rejected": 1,
                  "quarantined": 1, "conflicts": 0, "warnings": 0})
        row = query("SELECT * FROM ingestion_run WHERE id=%s", (run_id,))[0]
        assert row["stage"] == "PRODUCTION"
        assert row["activation_status"] == "ACTIVE"
        assert row["rows_accepted"] == 9 and row["rows_rejected"] == 1
        t2 = IngestionRunTracker("synthetic_fixtures", "FC26")
        rid2 = t2.start(rows_raw=5)
        t2.fail("boom")
        row2 = query("SELECT * FROM ingestion_run WHERE id=%s", (rid2,))[0]
        assert row2["stage"] == "FAILED"
        assert row2["activation_status"] == "REJECTED"
        assert "boom" in row2["report"]["failure"]
        # unknown version refuses (§25)
        t3 = IngestionRunTracker("synthetic_fixtures", "FC99")
        with pytest.raises(LookupError):
            t3.start()
        execute("DELETE FROM ingestion_quarantine WHERE run_id IN (%s,%s)",
                (run_id, rid2))
        execute("DELETE FROM ingestion_run WHERE id IN (%s,%s)", (run_id, rid2))
