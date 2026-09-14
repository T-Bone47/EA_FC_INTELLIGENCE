"""Recommendation-level confidence.

Confidence answers: "how much of the weighted decision rests on KNOWN
evidence?" — computed deterministically from component statuses plus entity
data confidence. A recommendation built on 2 known components out of 6 must
show lower confidence than one built on all 6.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.services.confidence_service import DataConfidence
from backend.services.fit_value import FitStatus, FitValue
from backend.services.scoring_config import COMPONENT_WEIGHTS


@dataclass
class RecommendationConfidence:
    score: float                        # 0..1
    evidence_coverage: float            # share of component weight that is KNOWN
    known_components: list[str]
    unknown_components: list[str]
    insufficient_components: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "evidence_coverage": round(self.evidence_coverage, 3),
            "known_components": self.known_components,
            "unknown_components": self.unknown_components,
            "insufficient_components": self.insufficient_components,
            "notes": self.notes,
        }


def compute(components: dict[str, FitValue],
            data_confidence: DataConfidence | None = None,
            weights: dict[str, float] | None = None) -> RecommendationConfidence:
    """weights: effective component weight table (default: baseline
    COMPONENT_WEIGHTS). v2.1 passes request-effective weights (e.g. incl.
    archetype_fit) so coverage reflects what actually drove the score."""
    w_table = weights if weights is not None else COMPONENT_WEIGHTS
    known, unknown, insufficient = [], [], []
    covered = 0.0
    for name, fv in components.items():
        if name not in w_table:
            continue                      # advisory (role_fit) doesn't change coverage
        if fv.status == FitStatus.KNOWN:
            known.append(name)
            covered += w_table[name]
        elif fv.status == FitStatus.UNKNOWN:
            unknown.append(name)
        else:
            insufficient.append(name)

    notes: list[str] = []
    if unknown:
        notes.append("no requirement/data for: " + ", ".join(sorted(unknown))
                     + " — weight redistributed, no penalty applied")
    if insufficient:
        notes.append("evidence insufficient for: " + ", ".join(sorted(insufficient)))
    if data_confidence is not None:
        notes.extend(data_confidence.notes[:3])
        score = 0.7 * covered + 0.3 * data_confidence.score
    else:
        score = covered
    return RecommendationConfidence(
        score=max(0.0, min(1.0, score)),
        evidence_coverage=covered,
        known_components=known,
        unknown_components=unknown,
        insufficient_components=insufficient,
        notes=notes,
    )
