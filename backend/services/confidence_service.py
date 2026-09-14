"""Data-level confidence: how trustworthy is what we know about an entity?

Deterministic aggregation over evidence availability. Feeds API "confidence"
fields and the data-freshness block. No ML.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.domain.card_model import Candidate, DataStatus

# Weight of each evidence dimension toward entity data confidence.
DIMENSIONS = {
    "identity_published": 0.15,     # name + nation + position present
    "attributes_coverage": 0.35,    # share of position-relevant attrs published
    "playstyles_published": 0.15,   # PlayStyle list published by source
    "provenance": 0.20,             # canonical + provenance-backed source
    "price_known": 0.15,            # only counts when price is relevant
}


@dataclass
class DataConfidence:
    score: float                     # 0..1
    dimension_scores: dict[str, float]
    notes: list[str]

    def to_dict(self) -> dict:
        return {"score": round(self.score, 3),
                "dimensions": {k: round(v, 3) for k, v in self.dimension_scores.items()},
                "notes": self.notes}


def entity_data_confidence(candidate: Candidate,
                           relevant_attributes: list[str],
                           price_relevant: bool = False) -> DataConfidence:
    """§29: pure per (candidate, relevant set, price_relevant) — memoized on
    the candidate feature cache; consumers are read-only."""
    cache = getattr(candidate, "feature_cache", None)
    ck = ("data_confidence", tuple(relevant_attributes), bool(price_relevant))
    if cache is not None and ck in cache:
        return cache[ck]
    out = _entity_data_confidence(candidate, relevant_attributes, price_relevant)
    if cache is not None:
        cache[ck] = out
    return out


def _entity_data_confidence(candidate: Candidate,
                            relevant_attributes: list[str],
                            price_relevant: bool = False) -> DataConfidence:
    notes: list[str] = []
    dims: dict[str, float] = {}

    identity = 1.0 if (candidate.name and candidate.nation and candidate.position_primary) else 0.5
    dims["identity_published"] = identity

    if relevant_attributes:
        have = sum(1 for a in relevant_attributes if candidate.attributes.get(a) is not None)
        dims["attributes_coverage"] = have / len(relevant_attributes)
        if have < len(relevant_attributes):
            notes.append(f"{len(relevant_attributes) - have} position-relevant "
                         f"attributes unpublished (UNKNOWN, not zero)")
    else:
        dims["attributes_coverage"] = 0.5
        notes.append("no position profile available to judge attribute coverage")

    dims["playstyles_published"] = 1.0 if candidate.playstyle_data_published else 0.0
    if not candidate.playstyle_data_published:
        notes.append("PlayStyles unpublished by source — PlayStyle facts UNKNOWN")

    dims["provenance"] = 1.0 if candidate.data_status == DataStatus.CANONICAL else 0.3
    if candidate.data_status != DataStatus.CANONICAL:
        notes.append(f"data_status={candidate.data_status.value}")

    if price_relevant:
        dims["price_known"] = 1.0 if candidate.price_coins is not None else 0.0
        if candidate.price_coins is None:
            notes.append("no verified market price — budget fit UNKNOWN")
        weights = DIMENSIONS
    else:
        weights = {k: v for k, v in DIMENSIONS.items() if k != "price_known"}
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

    score = sum(weights[k] * dims[k] for k in weights)
    return DataConfidence(score=score, dimension_scores=dims, notes=notes)
