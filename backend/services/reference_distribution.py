"""Frozen reference distributions for the v3 evidence interval (C_lo/C_hi).

Per INTELLIGENCE_MODEL_SPEC.md S4.3 and FC26_REFERENCE_DISTRIBUTION_SPEC.md:
missing demanded-attribute weight is charged at a frozen, versioned P10/P90
quantile, never a live query. This module builds that frozen table from a
dataset (once, offline) and loads it at runtime (read-only, cheap).

Universe tagging is load-bearing (FC26_DATA_TO_V3_MAPPING.md, contradiction
C-1): the only distribution buildable today describes ratings-site PLAYER
items. FC26 UT cards (TOTW, promos, Icons, Heroes) are a materially different,
upward-shifted population -- measured foundation OVRs diverge from reported
in-season FUT values by up to 11 points. Applying a player-derived P10 to a
card would systematically over-penalise exactly the special-card population
the product exists to reason about. The engine therefore refuses to apply a
RATINGS_SITE_PLAYERS distribution outside game_player scope.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

POSITION_GROUPS: dict[str, set[str]] = {
    "GK": {"GK"},
    "DEF": {"CB", "LB", "RB"},
    "MID": {"CDM", "CM", "CAM", "LM", "RM"},
    "ATT": {"LW", "RW", "ST"},
}


def position_group_for(position: str) -> Optional[str]:
    for group, members in POSITION_GROUPS.items():
        if position in members:
            return group
    return None


class Universe:
    RATINGS_SITE_PLAYERS = "RATINGS_SITE_PLAYERS"
    UT_CARDS = "UT_CARDS"


@dataclass(frozen=True)
class AttributeQuantiles:
    n: int
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class ReferenceDistribution:
    version: str
    game_version: str
    universe: str
    generated_at: str
    content_hash: str
    groups: dict[str, dict[str, AttributeQuantiles]]  # group -> attr -> quantiles
    # Phase 22. None on artifacts frozen before these fields existed (the
    # FC26 distribution); RESEARCH_ONLY distributions must say so explicitly.
    data_status: Optional[str] = None
    provenance: Optional[dict] = None

    def quantiles(self, position: str, attribute: str) -> Optional[AttributeQuantiles]:
        group = position_group_for(position)
        if group is None:
            return None
        return self.groups.get(group, {}).get(attribute)

    def applies_to(self, entity_type: str) -> bool:
        """Refuse to score a ut_card against a player-only distribution.
        This is the enforcement point for FC26_DATA_TO_V3_MAPPING.md C-1."""
        return (self.universe, entity_type) in {
            (Universe.RATINGS_SITE_PLAYERS, "game_player"), (Universe.UT_CARDS, "ut_card"),
        }

    def to_json(self) -> dict:
        out = {
            "version": self.version,
            "game_version": self.game_version,
            "universe": self.universe,
            "generated_at": self.generated_at,
            "content_hash": self.content_hash,
            "groups": {
                g: {a: {"n": q.n, "p10": q.p10, "p50": q.p50, "p90": q.p90}
                    for a, q in attrs.items()}
                for g, attrs in self.groups.items()
            },
        }
        if self.data_status is not None:
            out["data_status"] = self.data_status
        if self.provenance is not None:
            out["provenance"] = self.provenance
        return out

    @staticmethod
    def from_json(d: dict) -> "ReferenceDistribution":
        groups = {
            g: {a: AttributeQuantiles(**q) for a, q in attrs.items()}
            for g, attrs in d["groups"].items()
        }
        if _content_hash(groups) != d["content_hash"]:
            raise ReferenceDistributionMismatch(
                f"Frozen reference {d['version']!r} quantiles disagree with its content hash")
        return ReferenceDistribution(
            version=d["version"], game_version=d["game_version"],
            universe=d["universe"], generated_at=d["generated_at"],
            content_hash=d["content_hash"], groups=groups,
            data_status=d.get("data_status"), provenance=d.get("provenance"),
        )


def _content_hash(groups: dict[str, dict[str, AttributeQuantiles]]) -> str:
    canonical = json.dumps(
        {g: {a: [q.n, q.p10, q.p50, q.p90] for a, q in sorted(attrs.items())}
         for g, attrs in sorted(groups.items())},
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _interpolated_quantile(sorted_vals: list[float], p: float) -> float:
    """Linear interpolation between order statistics. Fixed by specification
    (INTELLIGENCE_MODEL_SPEC.md S4.3) -- the estimator is versioned, not
    configurable, because changing it changes every score."""
    if not sorted_vals:
        raise ValueError("empty sample")
    n = len(sorted_vals)
    f = p * (n - 1)
    lo = int(f)
    hi = min(lo + 1, n - 1)
    r = f - lo
    return round(sorted_vals[lo] * (1 - r) + sorted_vals[hi] * r, 4)


def build_from_rows(
    rows: list[dict],
    *,
    attribute_columns: list[str],
    position_field: str,
    version: str,
    game_version: str,
    universe: str,
    generated_at: str,
    min_n: int = 50,
    q_lo: float = 0.10,
    q_hi: float = 0.90,
) -> ReferenceDistribution:
    """Build a frozen reference distribution from row dicts (e.g. csv.DictReader
    output, or DB cursor rows mapped to dicts). Deterministic and reproducible:
    same rows + same parameters -> byte-identical content_hash."""
    groups: dict[str, dict[str, AttributeQuantiles]] = {g: {} for g in POSITION_GROUPS}
    for group, positions in POSITION_GROUPS.items():
        members = [r for r in rows if r.get(position_field) in positions]
        for attr in attribute_columns:
            vals: list[float] = []
            for r in members:
                v = r.get(attr)
                if v is None or v == "":
                    continue
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    continue
            if len(vals) < min_n:
                continue  # attribute stays UNKNOWN for this group -- never guessed
            vals.sort()
            groups[group][attr] = AttributeQuantiles(
                n=len(vals),
                p10=_interpolated_quantile(vals, q_lo),
                p50=_interpolated_quantile(vals, 0.5),
                p90=_interpolated_quantile(vals, q_hi),
            )

    return ReferenceDistribution(
        version=version, game_version=game_version, universe=universe,
        generated_at=generated_at, content_hash=_content_hash(groups), groups=groups,
    )


class ReferenceDistributionUnavailable(Exception):
    """Raised when no frozen distribution exists for a requested
    (game_version, universe), or when a distribution exists but its universe
    does not cover the requested entity scope. This is a refusal, not a
    fallback -- callers must not substitute a live computation."""


class ReferenceDistributionMismatch(ReferenceDistributionUnavailable):
    """A distribution exists but belongs to another game version, universe,
    or entity scope than the request. Refused -- never substituted."""


_CACHE: dict[tuple[str, str], tuple[tuple[int, int, int], ReferenceDistribution]] = {}


def default_artifact_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "reference_distributions"


def research_artifact_path() -> Path:
    """RESEARCH_ONLY distributions live apart from the production artifact
    directory, so the production loader cannot reach them by name."""
    return default_artifact_path() / "research"


def load_reference_distribution(version: str, *, artifact_dir: Optional[Path] = None) -> ReferenceDistribution:
    """Load a frozen distribution by version string. Never computes live.
    Defaults to the production artifact directory."""
    directory = artifact_dir or default_artifact_path()
    key = (str(directory), version)
    path = directory / f"{version}.json"
    try:
        stat = path.stat()
    except OSError as exc:
        raise ReferenceDistributionUnavailable(f"Frozen reference {version!r} is unavailable.") from exc
    stamp = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    cached = _CACHE.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        with path.open(encoding="utf-8") as f:
            dist = ReferenceDistribution.from_json(json.load(f))
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
        raise ReferenceDistributionMismatch(f"Invalid frozen reference {version!r}") from exc
    if dist.version != version:
        raise ReferenceDistributionMismatch("Frozen reference version disagrees with filename")
    _CACHE[key] = (stamp, dist)
    return dist


# (game_version, universe) -> the frozen distribution for that population.
# research_only entries are loadable only by an explicit research caller.
_REFERENCE_REGISTRY: dict[tuple[str, str], dict] = {
    ("FC26", Universe.RATINGS_SITE_PLAYERS): {
        "version": "fc26-players-2026-09-r1", "research_only": False},
    ("FC27", Universe.RATINGS_SITE_PLAYERS): {
        "version": "fc27-players-2026-09-r1", "research_only": True},
}


def check_reference_compatible(dist: ReferenceDistribution, *, game_version: str,
                               entity_type: str,
                               universe: str = Universe.RATINGS_SITE_PLAYERS) -> None:
    """Raise ReferenceDistributionMismatch unless `dist` describes exactly the
    requested version, universe and entity scope."""
    gv = str(game_version).strip().upper()
    if str(dist.game_version).upper() != gv:
        raise ReferenceDistributionMismatch(
            f"reference distribution {dist.version!r} is {dist.game_version}; request is {gv}. "
            "A distribution is never applied across game versions.")
    if dist.universe != universe:
        raise ReferenceDistributionMismatch(
            f"reference distribution {dist.version!r} universe {dist.universe} != {universe}")
    if not dist.applies_to(entity_type):
        raise ReferenceDistributionMismatch(
            f"reference distribution {dist.version!r} ({dist.universe}) does not apply to "
            f"entity scope {entity_type!r}")


def load_reference_for(game_version: str, *, entity_type: str = "game_player",
                       universe: str = Universe.RATINGS_SITE_PLAYERS,
                       allow_research_only: bool = False) -> ReferenceDistribution:
    """Resolve the frozen distribution for (game_version, universe) and verify
    it. A RESEARCH_ONLY distribution is refused unless the caller explicitly
    allows research data; the production path never does."""
    gv = str(game_version).strip().upper()
    entry = _REFERENCE_REGISTRY.get((gv, universe))
    if entry is None:
        raise ReferenceDistributionUnavailable(
            f"no reference distribution registered for ({gv}, {universe})")
    if entry["research_only"] and not allow_research_only:
        raise ReferenceDistributionUnavailable(
            f"the only {gv} reference distribution ({entry['version']}) is built from "
            "RESEARCH_ONLY data and is not available to the production path")
    directory = research_artifact_path() if entry["research_only"] else default_artifact_path()
    dist = load_reference_distribution(entry["version"], artifact_dir=directory)
    check_reference_compatible(dist, game_version=gv, entity_type=entity_type, universe=universe)
    if entry["research_only"] and dist.data_status != "RESEARCH_ONLY":
        raise ReferenceDistributionMismatch(
            f"{entry['version']} is registered research-only but the artifact says "
            f"data_status={dist.data_status!r}")
    return dist

def resolve_serving_reference(game_version, scope, research, environment, override=None):
    """Resolve only registered snapshots and authorize the result on every request, including cache hits."""
    from backend.services.data_license_gate import DataLicenseGateFailure, Environment, gate_or_raise
    if scope == "ut_card" and research:
        raise ReferenceDistributionMismatch("The player research opt-in cannot select a card reference.")
    universe = Universe.UT_CARDS if scope == "ut_card" else Universe.RATINGS_SITE_PLAYERS
    if environment == Environment.PRODUCTION:
        entry = _REFERENCE_REGISTRY.get((str(game_version).strip().upper(), universe))
        if entry and (research or not entry["research_only"]):
            gate_or_raise(entry["version"], environment=environment, game_version=game_version,
                          entity_scope=scope, allow_research_only=entry["research_only"] and research)
    ref = load_reference_for(game_version, entity_type=scope, universe=universe, allow_research_only=research)
    if override is not None and override != ref.version:
        raise ReferenceDistributionMismatch(f"{override!r} is not the registered reference for {game_version}")
    restricted = ref.data_status == "RESEARCH_ONLY"
    if restricted and not research:
        raise DataLicenseGateFailure("Research reference requires explicit opt-in")
    gate_or_raise(ref.version, environment=environment, game_version=game_version, entity_scope=scope,
                  allow_unverified=not restricted and environment in (Environment.LOCAL, Environment.RESEARCH),
                  allow_research_only=restricted and research)
    return ref, restricted
