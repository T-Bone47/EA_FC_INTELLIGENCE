import json
import os
import uuid
from urllib.parse import urlparse

import psycopg
import pytest

from backend.ingestion import fc27_research_profile as fc27
from backend.services import reference_distribution as refs
from backend.tests.conftest import requires_db
from scripts import build_field_provenance_v3 as provenance
from scripts import build_reference_distribution_v3 as reference_builder


def test_frozen_reference_rejects_changed_quantiles_with_original_checksum(tmp_path):
    version = fc27.REFERENCE_DISTRIBUTION_VERSION
    artifact = refs.load_reference_for("FC27", allow_research_only=True).to_json()
    artifact["groups"]["MID"]["short_passing"]["p10"] += 1
    (tmp_path / f"{version}.json").write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(refs.ReferenceDistributionMismatch, match="content hash"):
        refs.load_reference_distribution(version, artifact_dir=tmp_path)


@requires_db
@pytest.mark.skipif(urlparse(os.environ.get("DATABASE_URL", "")).path != "/eafc_ci",
                    reason="requires disposable eafc_ci")
def test_reference_and_provenance_use_bound_fc27_snapshot():
    url = os.environ["DATABASE_URL"]
    expected_observation = provenance.select_observation(fc27.GAME_VERSION, fc27.SOURCE_ID)
    player_id = uuid.uuid4()
    with psycopg.connect(url) as conn:
        version_id = conn.execute("SELECT id FROM game_version WHERE code = 'FC27'").fetchone()[0]
        unbound_observation = conn.execute("""
            INSERT INTO source_observation (source_id, game_version_id, entity_type, snapshot_date)
            VALUES (%s, %s, 'snapshot', %s) RETURNING id
        """, (fc27.SOURCE_ID, version_id, fc27.SNAPSHOT_DATE)).fetchone()[0]
        conn.execute("""
            INSERT INTO game_player (id, game_version_id, source_id, source_player_id,
                normalized_name, display_name, position_primary, gender, data_status, overall_rating)
            VALUES (%s, %s, %s, 99999999, 'unbound fixture', 'Unbound fixture', 'CM', 'fixture',
                    'RESEARCH_ONLY', 80)
        """, (player_id, version_id, fc27.SOURCE_ID))
    try:
        assert provenance.select_observation(fc27.GAME_VERSION, fc27.SOURCE_ID) == expected_observation
        rows = reference_builder.fetch_rows(fc27.GAME_VERSION, fc27.DATA_STATUS)
        assert len(rows) == fc27.EXPECTED_ROW_COUNT
        assert all(row["gender"] != "fixture" for row in rows)
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM game_player WHERE id=%s", (player_id,))
            conn.execute("DELETE FROM source_observation WHERE id=%s", (unbound_observation,))
