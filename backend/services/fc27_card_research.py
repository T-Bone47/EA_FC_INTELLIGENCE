"""Owner-supplied local card release. There are no writes to the serving catalogue."""
import hashlib
import json
import uuid
from functools import lru_cache

from backend.core import db
from backend.domain.card_model import Candidate, DataStatus, GameVersionCode, PlayerAttributes
from backend.ingestion.fc27_source_evidence import SOURCES
from backend.services.reference_distribution import (
    ReferenceDistributionMismatch, Universe, load_reference_distribution, research_artifact_path,
)
from backend.services.recommendation_service_v3 import RecommendationServiceV3

SOURCE = SOURCES[3]
SNAPSHOT = "fc27-" + SOURCE.sha
RELEASE = "fc27-card-items-local-r1"
MEMBERS_DIGEST = "7ea30715c31dc9effc47452b61b7a64b875efa852684d34bb6292d82c18780c1"
REFERENCE_DIGEST = "54e60afe5b60c4db28a425b266153c5dd320773887188a5bac821268526239ff"


def validate_cached_membership():
    # Both source tables are append-only. A new row under the same snapshot ID
    # invalidates the already verified in-memory release.
    row = db.query_one("SELECT count(*) AS n FROM fc27_staging.observation WHERE snapshot_id=%s", (SNAPSHOT,))
    if not row or row["n"] != SOURCE.rows:
        raise ValueError("Pinned research membership changed.")
    return row["n"]


def staged_cards():
    return db.query("""
        SELECT o.record_id, o.normalized, o.identity_review
        FROM fc27_staging.observation o JOIN fc27_staging.snapshot s USING (snapshot_id)
        WHERE s.snapshot_id=%s AND s.sha256=%s AND s.source_id=%s
          AND s.manifest->>'game_version'='FC27' AND s.manifest->>'schema_version'='card-item-v1'
          AND s.manifest->>'production_reuse_scope'='NONE' AND s.manifest->>'validation_status'='PASS'
          AND s.manifest->>'source_rights_status'='UNKNOWN'
        ORDER BY o.source_row_number
    """, (SNAPSHOT, SOURCE.sha, SOURCE.source_id))


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode()).hexdigest()


def local_release(database_url):
    pool = _item_pool(database_url)
    return _card_reference(), pool


def _card_reference():
    ref = load_reference_distribution(RELEASE, artifact_dir=research_artifact_path())
    if (ref.version, ref.game_version, ref.universe, ref.data_status, ref.content_hash, ref.provenance) != (
        RELEASE, "FC27", Universe.UT_CARDS, "RESEARCH_ONLY", REFERENCE_DIGEST,
        {"snapshot_id": SNAPSHOT, "members_sha256": MEMBERS_DIGEST, "source_id": SOURCE.source_id}
    ):
        raise ReferenceDistributionMismatch("Incompatible local card research reference.")
    return ref


@lru_cache(maxsize=1)
def _item_pool(database_url):
    rows = staged_cards()
    if len(rows) != SOURCE.rows or digest(rows) != MEMBERS_DIGEST:
        raise ValueError("Card research release missing or differs from pinned observations.")
    pool = []
    for row in rows:
        card = row["normalized"]
        styles = card["playstyles"]
        pool.append(Candidate(
            entity_type="ut_card", entity_id=uuid.uuid5(uuid.NAMESPACE_URL, SNAPSHOT + "/" + row["record_id"]),
            game_version=GameVersionCode.FC27, name=card["player_name"] or card["full_name"],
            position_primary=card["position_primary"], secondary_positions=card["observed_positions"][1:],
            attributes=PlayerAttributes(card["attributes"]), overall_rating=card["overall_rating"],
            playstyles_base=styles["base"], playstyles_plus=styles["plus"],
            playstyle_data_published=bool(styles["base"] or styles["plus"]),
            league=card["league"], nation=card["nation"], club=card["club"], rarity=card["rarity"],
            data_status=DataStatus.RESEARCH_ONLY,
            extra={"source_item_id": row["record_id"], "identity_status": row["identity_review"]["status"],
                   "confirmed_base_id": (row["identity_review"].get("candidate_base_id")
                                         if row["identity_review"]["status"] == "RESOLVED" else None),
                   "editorial_role_fit": card.get("unverified_editorial_role_fit"),
                   "position_issues": [issue for issue in card["issues"] if isinstance(issue, dict)
                                       and issue.get("field") == "positions"]},
        ))
    return pool


# Tests and maintenance scripts reset the immutable pool between databases.
local_release.cache_clear = _item_pool.cache_clear


def card_facts(card):
    return {"entity_id": str(card.entity_id), "source_item_id": card.extra["source_item_id"],
            "name": card.name, "rarity": card.rarity, "overall": card.overall_rating,
            "positions": [card.position_primary, *card.secondary_positions],
            "position_issues": card.extra["position_issues"], "source_snapshot_id": SNAPSHOT,
            "base_identity_status": card.extra["identity_status"],
            "playstyles": {"base": card.playstyles_base, "plus": card.playstyles_plus}
                         if card.playstyle_data_published else None,
            "editorial_role_fit": card.extra["editorial_role_fit"], "official_roles": None,
            "market_price": None, "chemistry": None}


class ResearchCards(RecommendationServiceV3):
    """Use the same rank, comparison, context and explanation code as the public service."""
    def __init__(self, reference, candidates):
        self.reference = reference
        self.candidates = candidates

    def _resolve(self, body):
        if body.game_version != "FC27" or body.entity_scope != "ut_card" or not body.include_research_data:
            raise ValueError("Explicit FC27 card research scope required")
        return self.reference, True

    def _pool(self, body, research):
        # Restrict research recommendations to positions explicitly observed on the item.
        return [c for c in self.candidates if body.position in (c.position_primary, *c.secondary_positions)]

    def _entry(self, rc, by_id, body, top_n):
        row = super()._entry(rc, by_id, body, top_n)
        row["card"].update(card_facts(by_id[row["entity_id"]]))
        return row
