"""ENGINE CONFIG — explicit, tunable configuration for Intelligence Engine v2.1.

Every new intelligence layer reads its parameters from here (§46: no magic
numbers scattered in scoring code). Baseline V2 tables stay in
`scoring_config.py` UNCHANGED; this module only ADDS.

Ground rules encoded by these tables:
  * Archetypes, gameplay profiles, slot duties and tactical dimensions are
    ENGINE-DERIVED conventions — never presented as official EA facts.
  * Qualitative bands are configurable mappings, NOT objective universal
    truths (§11). They translate user language into soft targets; they never
    fabricate data.
  * PlayStyle names used in affinity tables must exist in the ingested
    `playstyle_definition` vocabulary (36 names, FC26) — validated by tests.
  * Fit scores are suitability, not probabilities (§23).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Engine identity (§60) — scoring semantics are versioned; changes require an
# ENGINE_CHANGELOG entry.
# ---------------------------------------------------------------------------
ENGINE_VERSION = "2.3.0"

# ---------------------------------------------------------------------------
# §11 — qualitative target bands.
# band -> soft target attribute value. Used ONLY as a soft preference target
# (score ramps toward it); never as a hard floor unless the user explicitly
# demanded a numeric minimum. Mapping is a documented, tunable convention.
# ---------------------------------------------------------------------------
QUALITY_BANDS: dict[str, int] = {
    "elite": 90,
    "excellent": 85,
    "very_good": 80,
    "good": 75,
    "average": 70,
    "weak": 62,
}
# ramp width below the band target (points) — mirrors the legacy min-ramp (25)
BAND_RAMP_POINTS = 25.0

# ---------------------------------------------------------------------------
# §10 — diminishing returns (saturation).
# Above the knee, extra points count at SATURATION_EXCESS_FACTOR. Applied only
# on the opt-in intelligence path (enable_saturation) — legacy v/99 unchanged.
# Per-attribute-class knees; attributes not listed use DEFAULT_KNEE.
# ---------------------------------------------------------------------------
SATURATION_KNEES: dict[str, int] = {
    # pace class: beyond ~90 the marginal tactical gain shrinks
    "pace": 90, "acceleration": 90, "sprint_speed": 90,
    # passing/class: beyond ~88
    "short_passing": 88, "long_passing": 88, "vision": 88, "crossing": 88,
    "curve": 88,
    # finishing class
    "finishing": 88, "shot_power": 88, "long_shots": 88, "volleys": 88,
    # defending class
    "defending": 88, "standing_tackle": 88, "interceptions": 88,
    "defensive_awareness": 88, "sliding_tackle": 88,
    # physical/technical
    "strength": 88, "stamina": 90, "aggression": 85, "jumping": 88,
    "heading_accuracy": 88, "dribbling_detail": 88, "ball_control": 88,
    "agility": 88, "balance": 88, "reactions": 88, "composure": 88,
    "positioning": 88, "free_kick_accuracy": 85, "penalties": 85,
}
DEFAULT_SATURATION_KNEE = 88
SATURATION_EXCESS_FACTOR = 0.35   # each point above the knee counts 0.35

# ---------------------------------------------------------------------------
# §9 — controlled attribute interaction features.
# Each feature: attrs (ALL must be KNOWN else the feature is skipped —
# honesty over guessing), op (min | geo), and the contexts where it applies
# (positions and/or tactical profiles). weight = share of attribute_fit the
# interaction block may contribute (renormalized with the base attributes).
# ---------------------------------------------------------------------------
INTERACTION_FEATURES: dict[str, dict] = {
    "explosive_ball_carrier": {
        "attrs": ("acceleration", "dribbling_detail", "agility"),
        "op": "geo",
        "positions": ("LW", "RW", "LM", "RM", "ST", "CAM"),
        "profiles": ("PACE_ABUSER", "DRIBBLE_HEAVY", "COUNTER_ATTACK"),
        "weight": 0.15,
        "why": "pace + dribbling + agility together create explosiveness; each alone overstates it",
    },
    "pressing_engine": {
        "attrs": ("stamina", "aggression", "interceptions"),
        "op": "min",
        "positions": ("CM", "CDM", "ST", "LW", "RW", "CAM"),
        "profiles": ("PRESSING",),
        "weight": 0.15,
        "why": "pressing needs the WEAKEST of engine/work-rate/reading of the game to hold up",
    },
    "playmaker_hub": {
        "attrs": ("vision", "short_passing", "composure"),
        "op": "geo",
        "positions": ("CM", "CAM", "CDM"),
        "profiles": ("POSSESSION", "BUILD_UP", "FAST_BUILD_UP"),
        "weight": 0.15,
        "why": "creation under pressure is vision × passing × composure, not their sum",
    },
    "poacher_instinct": {
        "attrs": ("positioning", "finishing", "reactions"),
        "op": "geo",
        "positions": ("ST",),
        "profiles": ("COUNTER_ATTACK", "CROSSING", "LONG_SHOT"),
        "weight": 0.15,
        "why": "chance conversion compounds: being in the right place only pays with the finish",
    },
    "defensive_wall": {
        "attrs": ("standing_tackle", "defensive_awareness", "strength"),
        "op": "min",
        "positions": ("CB", "CDM", "LB", "RB"),
        "profiles": ("PRESSING", "DIRECT_PLAY", "LOW_BLOCK", "MID_BLOCK"),
        "weight": 0.15,
        "why": "duel reliability is limited by the weakest of tackle/awareness/physicality",
    },
    "transition_launcher": {
        "attrs": ("long_passing", "vision", "ball_control"),
        "op": "geo",
        "positions": ("CDM", "CM", "LB", "RB", "CB"),
        "profiles": ("COUNTER_ATTACK", "FAST_BUILD_UP", "DIRECT_PLAY"),
        "weight": 0.12,
        "why": "launching transitions needs range plus the first touch to escape pressure",
    },
    "aerial_dominance": {
        "attrs": ("heading_accuracy", "jumping", "strength"),
        "op": "min",
        "positions": ("CB", "ST", "CDM"),
        "profiles": ("CROSSING", "DIRECT_PLAY", "LONG_SHOT"),
        "weight": 0.12,
        "why": "aerial duels require height-use, timing and physicality together",
    },
}
INTERACTION_TOTAL_CAP = 0.30   # interactions may never exceed this share of attribute_fit

# ---------------------------------------------------------------------------
# §23 — score bands. Semantics: ENGINE SUITABILITY, not probability.
# (threshold_inclusive, band, human meaning)
# ---------------------------------------------------------------------------
SCORE_BANDS: tuple[tuple[float, str, str], ...] = (
    (0.90, "EXCEPTIONAL_FIT", "fits the requested context on nearly every scored dimension"),
    (0.80, "STRONG_FIT", "strong fit with minor tradeoffs"),
    (0.70, "GOOD_FIT", "solid fit; clear weaknesses exist but do not break the role"),
    (0.60, "SITUATIONAL_FIT", "works in this context with caveats; compare alternatives"),
    (0.00, "WEAK_FIT", "poor fit for this specific request (not a verdict on the player)"),
)

# ---------------------------------------------------------------------------
# §37/§38 — counterfactuals + sensitivity.
# Counterfactual variants are re-scorings of the TOP-N under a modified
# request; everything is deterministic and cheap (no pool reload).
# ---------------------------------------------------------------------------
COUNTERFACTUAL_TOP_N = 20
COUNTERFACTUAL_PROFILE_ALTERNATIVES = ("POSSESSION", "PRESSING", "COUNTER_ATTACK", "BALANCED")
SENSITIVITY_MIN_SWING = 0.005   # weighted delta below this is noise, not a driver

# §51/§23: a score computed from less than this share of total component weight
# must NOT be labeled with a qualitative fit band — thin evidence is flagged as
# INSUFFICIENT_EVIDENCE at the interpretation layer even though the score itself
# stays legacy-exact (UNKNOWN components never lower scores).
MIN_BAND_EVIDENCE = 0.5

# ---------------------------------------------------------------------------
# §64 — diversity in alternatives
# ---------------------------------------------------------------------------
DIVERSITY_SCAN_TOP_N = 50       # scan window for best_alternative_archetype

# ---------------------------------------------------------------------------
# §72/§74 — explicit OVR-stance bias (only applied when the user asks; the
# overall_quality weight is scaled and the table renormalized).
# ---------------------------------------------------------------------------
OVERALL_BIAS_FACTORS = {"low": 0.5, "normal": 1.0, "high": 1.5}

# ---------------------------------------------------------------------------
# §20 — replacement verdicts
# ---------------------------------------------------------------------------
REPLACEMENT_UPGRADE_MARGIN = 0.02    # score delta beyond noise to call UPGRADE
REPLACEMENT_SACRIFICE_CRITICAL = 0.15  # a component drop beyond this is "critical"

# ---------------------------------------------------------------------------
# §24 — confidence 2.0 composition (ADDITIVE block; legacy confidence intact)
# ---------------------------------------------------------------------------
CONFIDENCE_V2_WEIGHTS = {
    "legacy_confidence": 0.55,
    "freshness": 0.20,
    "source_authority": 0.15,
    "identity": 0.10,
}
# freshness decay: days since last source observation -> factor (linear to floor)
FRESHNESS_FULL_DAYS = 180      # <= 180 days old: factor 1.0
FRESHNESS_FLOOR_DAYS = 730     # >= 730 days: factor 0.4 (never 0 — stale != false)
FRESHNESS_FLOOR_FACTOR = 0.4
# authority: tier 1 (official) -> 1.0 ... tier 5 -> 0.4 (documented mapping)
AUTHORITY_TIER_FACTOR = {1: 1.0, 2: 0.9, 3: 0.8, 4: 0.6, 5: 0.4}
CONFIDENCE_LEVELS = ((0.85, "HIGH"), (0.65, "MEDIUM"), (0.40, "LOW"), (0.0, "VERY_LOW"))

# ---------------------------------------------------------------------------
# §12/§13 — contextual PlayStyle value (see playstyle_context.py for tables).
# PlayStyle+ contextual multiplier bounds (never an automatic win):
# ---------------------------------------------------------------------------
PLAYSTYLE_PLUS_CONTEXT_FLOOR = 0.5   # even a well-matched + caps below certainty
PLAYSTYLE_PLUS_CONTEXT_PEAK = 1.0
PLAYSTYLE_REDUNDANCY_FACTOR = 0.5    # a + of a playstyle also held at base tier

# ---------------------------------------------------------------------------
# §16 — gameplay profile thresholds (ENGINE-DERIVED labels)
# ---------------------------------------------------------------------------
GAMEPLAY_PROFILE_STRONG = 82   # attribute >= this supports the label
GAMEPLAY_PROFILE_WEAK = 68     # attribute <= this contradicts it

# ---------------------------------------------------------------------------
# §17 — versatility
# ---------------------------------------------------------------------------
VERSATILITY_MIN_ADJACENCY = 0.40   # only alternates at/above this count (no useless alts)
VERSATILITY_MAX_CREDIT = 3         # credit at most 3 alternate positions

# ---------------------------------------------------------------------------
# §18/§19 — squad structural fit (advisory in v2.1; weighting is a future,
# validated decision). Duplicate-archetype penalty applies to the ADVISORY
# squad_structural value only — never to chemistry (still UNKNOWN).
# ---------------------------------------------------------------------------
SQUAD_DUPLICATE_ARCHETYPE_FACTOR = 0.75  # second same-archetype candidate scales by this
SQUAD_COMPLEMENT_BONUS = 0.10            # verified complementary pairing bonus (advisory)

# ---------------------------------------------------------------------------
# Phase 3 §13-14 — CARD VALUE (marginal contextual utility per verified cost)
# Value is NEVER OVR/price. Utility comes from the contextual engine; cost
# comes from VERIFIED price observations only. No verified price => VALUE is
# UNAVAILABLE, never 0, never estimated.
VALUE_PRICE_UNIT = 1_000_000       # value score = marginal utility per 1M coins
VALUE_MIN_PRICE_COINS = 1          # divisor floor (guards /0; prices < 1 are invalid)
PRICE_FRESH_DAYS = 14              # <= 14d old: fresh
PRICE_STALE_DAYS = 60              # > 60d old: flagged stale in value assessments
# ---------------------------------------------------------------------------
# Phase 3 §15 — CHEMISTRY (architecture only; no verified FC26 rules exist)
CHEMISTRY_REQUIRE_VERIFIED_RULES = True   # never compute a chemistry score
                                          # without verified game rules
VALUE_RANK_TOP_N = 50              # how many top contextual results get a value rank (§14/§17)
BUDGET_COUNTERFACTUAL_STEP = 100_000   # §35: "+100K budget" card counterfactual
# ---------------------------------------------------------------------------
# Phase 3 §9 — CARD ROLE familiarity reference mapping.
# Card role rows (ut_card_role) carry the game's familiarity label; this table
# maps labels to the 0..1 familiarity scale used by role_fit. Configurable
# reference semantics (like rarity) — never a generic "has roles" bonus:
# only the REQUESTED role's familiarity is scored, and a card without role
# data stays INSUFFICIENT_EVIDENCE.
CARD_ROLE_FAMILIARITY_SCORES = {"ROLE_PLUS": 1.0, "ROLE": 0.75, "UNFAMILIAR": 0.15}
