"""Verify immutable PostgreSQL staging against the pinned archives, then freeze the local card reference."""
import argparse
import json
import os
from tempfile import NamedTemporaryFile
from dataclasses import replace
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from backend.core.config import get_settings
from backend.ingestion.fc27_source_evidence import audit, CARD_ATTRS
from backend.services import fc27_card_research as release
from backend.services.data_license_gate import Environment, environment_from_settings
from backend.services.reference_distribution import Universe, build_from_rows, research_artifact_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    if environment_from_settings(settings.environment) != Environment.LOCAL or urlparse(
            settings.database_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Select a local PostgreSQL research database")
    _, _, observations, _, _ = audit(args.archives, date(2026, 11, 23))
    expected = [{"record_id": key, "normalized": normalized, "identity_review": review}
                for key, _, _, normalized, review in observations[release.SNAPSHOT]]
    actual = release.staged_cards()
    if actual != expected:
        raise ValueError("Staged item membership, fields or identity evidence differs from source archives")
    member_hash = release.digest(actual)
    cards = [r["normalized"] for r in actual]
    ref = build_from_rows([{**c["attributes"], "position": c["position_primary"]} for c in cards],
                          attribute_columns=sorted(set(CARD_ATTRS.values())), position_field="position",
                          version=release.RELEASE, game_version="FC27", universe=Universe.UT_CARDS,
                          generated_at="2026-11-23")
    ref = replace(ref, data_status="RESEARCH_ONLY", provenance={"source_id": release.SOURCE.source_id,
                  "snapshot_id": release.SNAPSHOT, "members_sha256": member_hash})
    print(json.dumps({"members": len(cards), "members_sha256": member_hash, "reference_sha256": ref.content_hash,
                      "groups": {k: len(v) for k, v in ref.groups.items()}}))
    if (member_hash, ref.content_hash) != (release.MEMBERS_DIGEST, release.REFERENCE_DIGEST):
        raise ValueError("Population or reference digest differs from the reviewed release")
    path = research_artifact_path() / (release.RELEASE + ".json")
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        staged_path = Path(temp.name)
    try:
        with staged_path.open("w", encoding="utf-8") as out:
            json.dump(ref.to_json(), out, indent=2, sort_keys=True)
            out.write("\n")
        try:
            os.link(staged_path, path)
        except FileExistsError:
            if json.loads(path.read_text(encoding="utf-8")) != ref.to_json():
                raise ValueError("Frozen file differs. Use a new release identifier.")
    finally:
        staged_path.unlink()


if __name__ == "__main__":
    from backend.core.db import close_pool
    try:
        main()
    finally:
        close_pool()
