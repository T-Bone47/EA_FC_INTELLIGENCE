"""V3 intelligence engine configuration.

Every tunable constant is declared here, versioned, and tagged with its
calibration status. Per the implementation mandate: nothing is hardcoded
unexplained in scoring code, and nothing is frozen as if measured when it
has not been measured in THIS repository.

Calibration status vocabulary (mirrors the claim classes in the architecture
and model-spec documents):

    MEASURED    - swept and validated against real FC26 foundation data
                  and/or the adversarial golden set, in this repository.
    POLICY      - a product decision with no single objectively correct
                  value; a named owner should sign off before this changes.
    PLACEHOLDER - has no supporting measurement yet because the data that
                  would exercise it does not exist (e.g. kappa_min, whose
                  gate is measured to be inert on 100%-coverage player data).

Each config object carries its OWN `config_version`; a version string is never
reused for another value set. A recommendation response always carries the
version of the config that produced it so a stored result is replayable.

Versions (registry `CONFIGS`, lookup via `get_config`):
    v3-2026-09-17-r1    V3.1  FROZEN HISTORICAL  (missing_value_charge = P10)
    v3.2-2026-09-30-r1  V3.2  DEFAULT            (missing_value_charge = ZERO)
V3.2 differs from V3.1 in exactly one calibrated value (Phase 24, from the
Phase 23 finding that hiding a low published attribute could raise C_lo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# Historical V3.1 version string. FROZEN: never reused for another value set.
V3_1_CONFIG_VERSION = "v3-2026-09-17-r1"
# V3.2 (Phase 24): V3.1 constants unchanged; missing_value_charge P10 -> ZERO.
V3_2_CONFIG_VERSION = "v3.2-2026-09-30-r1"

# Valid categorical settings for missing_value_charge.
MISSING_CHARGE_MODES = ("P10", "ZERO")


class CalibrationStatus(str, Enum):
    MEASURED = "MEASURED"
    POLICY = "POLICY"
    PLACEHOLDER = "PLACEHOLDER"


@dataclass(frozen=True)
class CalibratedValue:
    value: float
    status: CalibrationStatus
    note: str


@dataclass(frozen=True)
class V3Config:
    # -- demand composition --------------------------------------------
    # Share of the composed demand vector coming from tactical dimensions
    # vs. the position base. MEASURED in this repository (see note): all
    # six product-thesis adversarial cases pass with healthy margins at
    # every value in [0.5, 0.8]; real-data tactical discrimination
    # (mean top-10 overlap across 5 profiles) at CB/ST clears the
    # <=6.0/10 target at lambda=0.7 (CB 5.0/10, ST 5.0/10); CM improves
    # from ~9.6/10 (v2) to 6.9/10 but does not clear the target at any
    # lambda <= 0.8 without discarding position knowledge entirely.
    # 0.7 is the considered default: it is the largest value in the
    # validated adversarial-safe range that also clears the real-data
    # target for two of three position groups tested.
    lam_default: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.70, CalibrationStatus.MEASURED,
        "Adversarial margins healthy for lambda in [0.5,0.8]; CB/ST real-data "
        "discrimination clears <=6.0/10 mean top-10 overlap at 0.7; CM does not "
        "(measured 6.9/10) -- see TEST_RESULTS.md RD-1. Per-request overridable."
    ))

    # -- evidence / coverage ---------------------------------------------
    # Below this coverage, a candidate is NOT_EVALUABLE rather than ranked.
    # PLACEHOLDER: measured coverage on the real 16,228-player foundation is
    # kappa ~= 1.00 at every percentile from P01 to P99 for every position
    # group tested (players publish essentially all demanded attributes).
    # The gate is therefore currently inert -- any threshold in [0, 1.0)
    # produces identical behaviour on today's data. It cannot be calibrated
    # from evidence until card-level partial publication exists. Kept at
    # the value proposed at the architecture stage, explicitly unproven.
    kappa_min: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.60, CalibrationStatus.PLACEHOLDER,
        "Gate is inert on current data (measured kappa ~1.00 at P01 across all "
        "position groups). No empirical basis yet; do not present as calibrated."
    ))
    kappa_band_min: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.75, CalibrationStatus.POLICY,
        "Qualitative score bands withheld below this coverage. Needs an owner."
    ))

    # -- position eligibility --------------------------------------------
    theta_pos: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.40, CalibrationStatus.POLICY,
        "Matches the pre-existing compatible_positions adjacency bar so the "
        "engine gate and the repository pre-filter agree by construction."
    ))

    # -- modifier bounds ---------------------------------------------------
    modifier_min: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.85, CalibrationStatus.POLICY,
        "PlayStyle/interaction effect sizes are UNKNOWN (no verified FC26 "
        "mechanic); bound kept tight so no single modifier can dominate "
        "capability. Revisit only if effect sizes become measurable."
    ))
    modifier_max: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        1.15, CalibrationStatus.POLICY,
        "See modifier_min."
    ))
    playstyle_modifier_cap: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.10, CalibrationStatus.POLICY,
        "Individual cap on the PlayStyle modifier's contribution to modifier_max/min."
    ))
    interaction_modifier_cap: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.10, CalibrationStatus.POLICY,
        "Individual cap on the attribute-interaction modifier's contribution."
    ))

    # -- saturation --------------------------------------------------------
    # Carried unchanged from the v2 SATURATION_KNEES / EXCESS_FACTOR design,
    # which is a MATH property (monotone, bounded), not re-derived here.
    saturation_excess_factor: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.35, CalibrationStatus.POLICY, "Carried from v2 engine_config.py unchanged."
    ))
    default_saturation_knee: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        88.0, CalibrationStatus.POLICY, "Carried from v2 engine_config.py unchanged."
    ))

    # -- tie-break -----------------------------------------------------
    tie_epsilon: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        0.005, CalibrationStatus.POLICY,
        "Reuses the pre-existing SENSITIVITY_MIN_SWING noise threshold so "
        "there is one definition of 'noise' in the system."
    ))

    # -- reference distribution ------------------------------------------
    reference_quantile_lo: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        10.0, CalibrationStatus.POLICY, "P10. Harsher (P05) over-penalises; gentler (P25) under-penalises."
    ))
    reference_quantile_hi: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        90.0, CalibrationStatus.POLICY, "P90."
    ))
    reference_min_n: CalibratedValue = field(default_factory=lambda: CalibratedValue(
        50.0, CalibrationStatus.POLICY,
        "Minimum sample size per (position_group, attribute). Real data clears "
        "this by 36x or more in every cell measured."
    ))

    # -- missing-evidence charge (Phase 23 finding, adopted in V3.2) ----------
    # What C_lo charges for an unpublished demanded attribute: "ZERO" (V3.2,
    # default) or "P10" (V3.1, historical). Measured (artifacts/phase23/lab):
    # under P10, hiding a published value below P10 RAISES C_lo; under ZERO it
    # never can, and on full-coverage player data (kappa = 1.0 everywhere) the
    # two produce identical rankings. Not a CalibratedValue because it is
    # categorical; reported by config_snapshot().
    missing_value_charge: str = "ZERO"
    # Identity of THIS value set (see module docstring). Not a calibrated value.
    config_version: str = V3_2_CONFIG_VERSION

    def __post_init__(self) -> None:
        if self.missing_value_charge not in MISSING_CHARGE_MODES:
            raise ValueError(
                f"missing_value_charge must be one of {MISSING_CHARGE_MODES}, "
                f"got {self.missing_value_charge!r}")


# Non-numeric settings carried alongside the CalibratedValue fields.
_CATEGORICAL_FIELDS = {
    "missing_value_charge": (CalibrationStatus.POLICY,
                             "C_lo charge for unpublished demanded attributes: ZERO (V3.2 default) | P10 (V3.1 historical)"),
}


# V3.2 = class defaults. V3.1 is reconstructed explicitly and kept reproducible.
V3_2_CONFIG = V3Config()
V3_1_CONFIG = V3Config(missing_value_charge="P10", config_version=V3_1_CONFIG_VERSION)
DEFAULT_V3_CONFIG = V3_2_CONFIG

CONFIGS = {c.config_version: c for c in (V3_1_CONFIG, V3_2_CONFIG)}


def get_config(config_version: str) -> "V3Config":
    """Resolve a recorded config_version to its config (replay / audit)."""
    return CONFIGS[config_version]


# Back-compat alias = version of the DEFAULT config. Engines stamp the version of
# the config object they were given (self.config.config_version), NOT this.
CONFIG_VERSION = DEFAULT_V3_CONFIG.config_version


def config_snapshot(cfg: "V3Config | None" = None) -> dict:
    """Serialisable snapshot of every constant, its value, and its
    calibration status -- used to populate ScoringContext.config_version
    metadata and to render the config transparently in API responses."""
    cfg = cfg or DEFAULT_V3_CONFIG
    out = {"config_version": cfg.config_version}
    for f in cfg.__dataclass_fields__:
        if f == "config_version":
            continue
        if f in _CATEGORICAL_FIELDS:
            status, note = _CATEGORICAL_FIELDS[f]
            out[f] = {"value": getattr(cfg, f), "status": status.value, "note": note}
            continue
        cv: CalibratedValue = getattr(cfg, f)
        out[f] = {"value": cv.value, "status": cv.status.value, "note": cv.note}
    return out
