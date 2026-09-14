"""STRUCTURED INTENT (§2, §3).

An intent is not a flat bag of values: every parsed requirement carries
  * value
  * source        — USER_TEXT | INFERRED | DEFAULT
  * confidence    — HIGH | MEDIUM | LOW
  * explicit      — True when the user literally stated it

Hard constraints and soft preferences are first-class and separate (§2):
  HARD — violating them normally removes a candidate (wrong version, budget
         when verified, explicit numeric minimums, mandatory PlayStyle/Role,
         league/club/nation requirements, min/max OVR when explicit).
  SOFT — missing them lowers the score, never eliminates (preferred traits,
         archetypes, bands, tactical suitability, value).

The parser must NOT invent facts: qualitative language maps to configurable
bands/archetypes (documented conventions), never to fabricated numeric data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SOURCES = ("USER_TEXT", "INFERRED", "DEFAULT")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")


@dataclass(frozen=True)
class IntentField:
    """One parsed requirement with full provenance."""
    name: str
    value: Any
    source: str = "USER_TEXT"
    confidence: str = "HIGH"
    explicit: bool = True
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return {"value": self.value, "source": self.source,
                "confidence": self.confidence, "explicit": self.explicit,
                **({"note": self.note} if self.note else {})}


@dataclass(frozen=True)
class HardConstraint:
    """A constraint that normally eliminates candidates when violated.
    `kind` is a stable machine-readable identifier; `enforced` says whether
    the engine can actually verify it with available data (e.g. budget is only
    enforceable when a verified price exists — otherwise it stays UNKNOWN and
    is reported, never assumed satisfied)."""
    kind: str                     # BUDGET | MIN_OVR | MAX_OVR | ATTRIBUTE_MIN |
                                  # REQUIRED_PLAYSTYLE | REQUIRED_LEAGUE |
                                  # REQUIRED_CLUB | REQUIRED_NATION | GAME_VERSION |
                                  # POSITION | SLOT
    field: str                    # e.g. attribute name / 'budget_coins'
    value: Any
    enforced: bool = True
    reason: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "field": self.field, "value": self.value,
                "enforced": self.enforced, "reason": self.reason}


@dataclass(frozen=True)
class SoftPreference:
    kind: str                     # ATTRIBUTE_BAND | ARCHETYPE | PLAYSTYLE |
                                  # TACTICAL | TRAIT | QUALITY_BIAS | COMPLEMENT
    field: str
    value: Any
    weight: float = 1.0
    source: str = "USER_TEXT"
    explicit: bool = True

    def to_dict(self) -> dict:
        return {"kind": self.kind, "field": self.field, "value": self.value,
                "weight": self.weight, "source": self.source, "explicit": self.explicit}


@dataclass
class ParsedIntent:
    """Full structured intent. `fields` is the provenance map for every
    emitted value; hard/soft lists drive constraint handling and scoring."""
    game_version: str
    fields: dict[str, IntentField] = field(default_factory=dict)
    hard_constraints: list[HardConstraint] = field(default_factory=list)
    soft_preferences: list[SoftPreference] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # ---- convenience accessors (None when not parsed) ----------------------
    def get(self, name: str) -> Any:
        f = self.fields.get(name)
        return f.value if f is not None else None

    def to_draft(self) -> dict:
        """Backward-compatible flat draft + additive provenance blocks."""
        draft: dict[str, Any] = {"game_version": self.game_version}
        for name in ("position", "formation", "slot", "tactical_profile",
                     "secondary_tactical_profile", "archetype", "budget_coins",
                     "overall_quality_bias", "complement_hint"):
            f = self.fields.get(name)
            if f is not None:
                draft[name] = f.value
        prefs = self.fields.get("attribute_preferences")
        if prefs is not None:
            draft["attribute_preferences"] = prefs.value
        bands = self.fields.get("attribute_bands")
        if bands is not None:
            draft["attribute_bands"] = bands.value
        dps = self.fields.get("desired_playstyles")
        if dps is not None:
            draft["desired_playstyles"] = dps.value
        rps = self.fields.get("required_playstyles")
        if rps is not None:
            draft["required_playstyles"] = rps.value
        draft["hard_constraints"] = [h.to_dict() for h in self.hard_constraints]
        draft["soft_preferences"] = [s.to_dict() for s in self.soft_preferences]
        draft["fields"] = {k: v.to_dict() for k, v in self.fields.items()}
        if self.unrecognized:
            draft["unrecognized_fragments"] = self.unrecognized
        draft["confidence_notes"] = list(self.notes)
        return draft
