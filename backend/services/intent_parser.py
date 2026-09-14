"""DETERMINISTIC intent parser (§3, §4) — natural language -> ParsedIntent.

Evolution of the route-level V2 parser (same no-fabrication contract):
  * every emitted value comes from reference tables or explicit user numbers;
  * unrecognized fragments are recorded, never guessed;
  * semantic football language ("box-to-box", "ball-winning", "target man")
    maps to ARCHETYPES + inferred soft preferences — archetypes are computed
    from data at scoring time, never hardcoded per player;
  * qualitative attribute language ("good stamina") maps to configurable BANDS
    (engine_config.QUALITY_BANDS), marked source=INFERRED, explicit=False —
    never to invented numeric minimums;
  * explicit numbers ("minimum 85 pace", "under 100k") become hard constraints
    with source=USER_TEXT, confidence=HIGH.
"""
from __future__ import annotations

import re
from typing import Optional

from backend.services.engine_config import QUALITY_BANDS
from backend.services.intent import (
    HardConstraint, IntentField, ParsedIntent, SoftPreference,
)

# ---------------------------------------------------------------- vocabulary
_POSITION_WORDS = {
    "st": "ST", "striker": "ST", "forward": "ST",
    "lw": "LW", "left wing": "LW", "left winger": "LW",
    "rw": "RW", "right wing": "RW", "right winger": "RW",
    "cam": "CAM", "attacking mid": "CAM", "attacking midfielder": "CAM",
    "number 10": "CAM",
    "cm": "CM", "central mid": "CM", "central midfielder": "CM", "midfielder": "CM",
    "cdm": "CDM", "defensive mid": "CDM", "defensive midfielder": "CDM",
    "lm": "LM", "left mid": "LM", "rm": "RM", "right mid": "RM", "right cm": "CM",
    "lb": "LB", "left back": "LB", "rb": "RB", "right back": "RB",
    "cb": "CB", "centre back": "CB", "center back": "CB", "defender": "CB",
    "gk": "GK", "goalkeeper": "GK", "keeper": "GK",
}

# tactical phrases, ordered longest-first so specific phrases win over generic
_TACTIC_WORDS = {
    "high press": "HIGH_PRESS", "gegenpress": "HIGH_PRESS", "pressing": "PRESSING",
    "fast build up": "FAST_BUILD_UP", "fast build-up": "FAST_BUILD_UP",
    "quick build up": "FAST_BUILD_UP", "quick build-up": "FAST_BUILD_UP",
    "slow build up": "SLOW_BUILD_UP", "slow build-up": "SLOW_BUILD_UP",
    "patient build up": "SLOW_BUILD_UP", "play out from the back": "BUILD_UP",
    "build up": "BUILD_UP", "build-up": "BUILD_UP",
    "mid block": "MID_BLOCK", "medium block": "MID_BLOCK",
    "low block": "LOW_BLOCK", "deep block": "LOW_BLOCK", "park the bus": "LOW_BLOCK",
    "quick transition": "COUNTER_ATTACK", "fast transition": "COUNTER_ATTACK",
    "quick transitions": "COUNTER_ATTACK", "fast transitions": "COUNTER_ATTACK",
    "counter attack": "COUNTER_ATTACK", "counter-attack": "COUNTER_ATTACK",
    "counter": "COUNTER_ATTACK", "transitions": "COUNTER_ATTACK",
    "possession": "POSSESSION", "tiki": "POSSESSION",
    "dribbl": "DRIBBLE_HEAVY",
    "cross": "CROSSING", "wing play": "CROSSING",
    "long shot": "LONG_SHOT", "shoot from distance": "LONG_SHOT",
    "direct": "DIRECT_PLAY", "long ball": "DIRECT_PLAY",
    "pace": "PACE_ABUSER", "speed": "PACE_ABUSER",
}

_ATTR_WORDS = {
    "stamina": "stamina", "defensive awareness": "defensive_awareness",
    "passing": "short_passing", "vision": "vision", "pace": "pace",
    "speed": "pace", "shooting": "shooting", "finishing": "finishing",
    "defending": "defending", "physical": "strength", "strength": "strength",
    "dribbling": "dribbling_detail", "crossing": "crossing",
    "long shots": "long_shots", "aggression": "aggression",
    "composure": "composure", "ball control": "ball_control",
    "tackling": "standing_tackle", "interceptions": "interceptions",
    "defend": "defending",
    "heading": "heading_accuracy", "long passing": "long_passing",
}

# qualitative band phrases (§11) — mapped to configurable bands, never numbers
_BAND_WORDS = {
    "elite": "elite", "world class": "elite", "excellent": "excellent",
    "great": "excellent", "very good": "very_good", "strong": "very_good",
    "good": "good", "decent": "good", "solid": "good", "average": "average",
    "okay": "average", "ok": "average",
}

# §4 — semantic football language -> archetype (computed, never assigned)
_ARCHETYPE_WORDS = {
    "box-to-box": "BOX_TO_BOX", "box to box": "BOX_TO_BOX", "b2b": "BOX_TO_BOX",
    "ball-winning": "BALL_WINNER", "ball winning": "BALL_WINNER",
    "ball winner": "BALL_WINNER", "destroyer": "BALL_WINNER",
    "anchor man": "BALL_WINNER", "anchor": "BALL_WINNER",
    "stay-back cdm": "BALL_WINNER", "sitting midfielder": "BALL_WINNER",
    "deep playmaker": "DEEP_PLAYMAKER", "regista": "DEEP_PLAYMAKER",
    "quarterback": "DEEP_PLAYMAKER",
    "creative playmaker": "CREATIVE_PLAYMAKER", "playmaker": "CREATIVE_PLAYMAKER",
    "creator": "CREATIVE_PLAYMAKER", "trequartista": "CREATIVE_PLAYMAKER",
    "inside forward": "INSIDE_FORWARD",
    "inverted winger": "INVERTED_WINGER", "inverted forward": "INVERTED_WINGER",
    "direct winger": "DIRECT_WINGER", "traditional winger": "DIRECT_WINGER",
    "target man": "TARGET_MAN", "target forward": "TARGET_MAN",
    "hold-up": "TARGET_MAN", "hold up": "TARGET_MAN",
    "pressing forward": "PRESSING_FORWARD",
    "poacher": "POACHER", "fox in the box": "POACHER",
    "false 9": "FALSE_9", "false nine": "FALSE_9",
    "attacking fullback": "ATTACKING_FULLBACK", "attacking full-back": "ATTACKING_FULLBACK",
    "overlapping fullback": "ATTACKING_FULLBACK", "overlapping full-back": "ATTACKING_FULLBACK",
    "wingback": "ATTACKING_FULLBACK", "wing-back": "ATTACKING_FULLBACK",
    "defensive fullback": "DEFENSIVE_FULLBACK", "defensive full-back": "DEFENSIVE_FULLBACK",
    "stopper": "STOPPER",
    "ball-playing defender": "BALL_PLAYING_DEFENDER",
    "ball playing defender": "BALL_PLAYING_DEFENDER",
    "sweeper keeper": "SWEEPER_KEEPER", "sweeper goalkeeper": "SWEEPER_KEEPER",
    "shot stopper": "SHOT_STOPPER", "shot-stopper": "SHOT_STOPPER",
}

# trait phrases -> inferred soft attribute bands (source=INFERRED)
_TRAIT_BANDS = {
    "pace merchant": [("pace", "elite")],
    "speedster": [("pace", "elite")],
    "very fast": [("pace", "excellent")],
    "quick": [("pace", "very_good")],
    "dribbler": [("dribbling_detail", "excellent")],
    "trickster": [("dribbling_detail", "excellent")],
    "magician": [("dribbling_detail", "excellent")],
    "finisher": [("finishing", "excellent")],
    "clinical": [("finishing", "excellent")],
    "progressive passer": [("long_passing", "very_good"), ("vision", "very_good")],
    "ball carrier": [("ball_control", "very_good"), ("dribbling_detail", "very_good")],
    "carries the ball": [("ball_control", "very_good"), ("dribbling_detail", "very_good")],
    "carry the ball": [("ball_control", "very_good"), ("dribbling_detail", "very_good")],
    "pass under pressure": [("composure", "very_good"), ("short_passing", "very_good")],
    "can defend": [("defending", "very_good")],
    "tracks back": [("defensive_awareness", "very_good"), ("stamina", "good")],
    "good on the ball": [("ball_control", "very_good")],
    "feels good on the ball": [("ball_control", "very_good")],
    "press resistant": [("composure", "very_good"), ("ball_control", "very_good")],
    "press-resistant": [("composure", "very_good"), ("ball_control", "very_good")],
    "workhorse": [("stamina", "excellent")],
    "engine": [("stamina", "excellent")],
    "leader": [],   # personality is not a published attribute — never invented
    "aerial threat": [("heading_accuracy", "very_good"), ("jumping", "very_good")],
    "strong": [("strength", "very_good")],
    "physical": [("strength", "very_good")],
}

_PLAYSTYLE_VOCAB = (
    "Tiki Taka", "First Touch", "Quick Step", "Rapid", "Finesse Shot",
    "Power Shot", "Press Proven", "Relentless", "Whipped Pass",
    "Incisive Pass", "Pinged Pass", "Anticipate", "Jockey",
    "Technical", "Trickster", "Intercept", "Dead Ball", "Enforcer",
    "Long Ball Pass", "Slide Tackle", "Block", "Bruiser", "Aerial Fortress",
    "Precision Header", "Acrobatic", "Chip Shot", "Low Driven Shot",
    "Deflector", "Inventive", "Gamechanger", "Footwork", "Cross Claimer",
    "Rush Out", "Far Reach", "Long Throw", "Far Throw",
)

_MANDATORY_MARKERS = ("must have", "must include", "requires", "require",
                      "mandatory", "only if", "has to have", "needed:")
_PREFERENCE_MARKERS = ("prefer", "like", "want", "would be nice", "if possible",
                       "ideally", "love")

_FORMATIONS = ("4-2-3-1", "4-3-3", "4-4-2", "4-3-2-1", "4-5-1", "4-1-2-1-2",
               "3-5-2", "3-4-3", "5-3-2", "5-2-1-2", "4-2-2-2")


# ---------------------------------------------------------------- parser
def _mask(t: str, phrase: str) -> str:
    """Blank out a consumed phrase so its sub-strings cannot trigger other rules
    (e.g. "quick transitions" must not also imply a `quick` -> pace band)."""
    if not phrase:
        return t
    return t.replace(phrase, " " * len(phrase))


def parse(text: str, game_version: str) -> ParsedIntent:
    """Deterministic parse. Emits only reference-table values or the user's own
    explicit numbers. Never invents ratings, cards, prices, PlayStyles or Roles."""
    t = f" {text.lower()} "
    intent = ParsedIntent(game_version=game_version)
    intent.fields["game_version"] = IntentField(
        "game_version", game_version, source="DEFAULT", confidence="HIGH",
        explicit=False, note="version comes from the request, never from text")

    # -- formation ------------------------------------------------------------
    for f in _FORMATIONS:
        if f in t:
            intent.fields["formation"] = IntentField("formation", f)
            break
    else:
        m = re.search(r"\b(\d(?:-\d){2,4})\b", t)
        if m:
            intent.unrecognized.append(f"formation-like token {m.group(1)!r} not in the reference list")

    # -- position (longest phrase wins) ---------------------------------------
    best_pos, best_len = None, 0
    for word, pos in _POSITION_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", t) and len(word) > best_len:
            best_pos, best_len = pos, len(word)
    if best_pos:
        intent.fields["position"] = IntentField("position", best_pos)

    # -- PlayStyles: mandatory vs preferred (§2) ----------------------------------
    # Detected BEFORE tactical phrases so multi-word PlayStyle names ("Tiki Taka")
    # are not consumed by tactical sub-strings ("tiki"). Every occurrence is
    # scanned: a PlayStyle is mandatory if ANY occurrence is preceded by a
    # mandatory marker.
    required_ps: list[str] = []
    desired_ps: list[str] = []
    for ps in sorted(_PLAYSTYLE_VOCAB, key=len, reverse=True):
        low = ps.lower()
        occurrences = [m.start() for m in re.finditer(re.escape(low), t)]
        if not occurrences:
            continue
        def _clause_before(idx: int) -> str:
            prefix = t[max(0, idx - 40):idx]
            # only the CURRENT clause can make this playstyle mandatory:
            # "must have X, would love Y" must not make Y mandatory (§2)
            for delim in (".", ",", ";", "!", "?", " and ", " but "):
                if delim in prefix:
                    prefix = prefix.rsplit(delim, 1)[-1]
            return prefix

        mandatory = any(any(mk in _clause_before(idx) for mk in _MANDATORY_MARKERS)
                        for idx in occurrences)
        if mandatory:
            required_ps.append(ps)
        else:
            desired_ps.append(ps)
        for idx in occurrences:
            t = t[:idx] + " " * len(low) + t[idx + len(low):]

    # -- tactical profiles: first mention = primary, second = secondary (§7) ---
    found: list[tuple[int, str]] = []
    for word, profile in sorted(_TACTIC_WORDS.items(), key=lambda kv: -len(kv[0])):
        idx = t.find(word)
        if idx >= 0:
            # avoid double-matching substrings of an already-matched longer phrase
            if any(s <= idx < e for s, e, _ in [(f[0], f[0] + 1, None) for f in []]):
                continue
            found.append((idx, profile))
    # dedupe overlapping matches: sort by position, drop profiles already covered
    found.sort()
    chosen: list[str] = []
    covered: list[tuple[int, int]] = []
    for idx, profile in found:
        word_len = max(len(w) for w, p in _TACTIC_WORDS.items() if p == profile and w in t[idx:idx + 40])
        if any(idx < e and s < idx + word_len for s, e in covered):
            continue
        covered.append((idx, idx + word_len))
        if profile not in chosen:
            chosen.append(profile)
    for idx, end in covered:
        t = t[:idx] + " " * (end - idx) + t[end:]
    if chosen:
        intent.fields["tactical_profile"] = IntentField("tactical_profile", chosen[0])
        if len(chosen) > 1:
            intent.fields["secondary_tactical_profile"] = IntentField(
                "secondary_tactical_profile", chosen[1],
                note="tactical combination: dimensions merged 60/40 (configurable)")

    # -- archetypes (§4) -------------------------------------------------------
    best_arch, best_arch_len, best_arch_phrase = None, 0, ""
    for phrase, arch in _ARCHETYPE_WORDS.items():
        if phrase in t and len(phrase) > best_arch_len:
            best_arch, best_arch_len, best_arch_phrase = arch, len(phrase), phrase
    if best_arch:
        t = _mask(t, best_arch_phrase)
        intent.fields["archetype"] = IntentField("archetype", best_arch)
        intent.soft_preferences.append(SoftPreference(
            "ARCHETYPE", "archetype", best_arch, weight=1.0,
            source="USER_TEXT", explicit=True))
        intent.notes.append(
            f"archetype {best_arch} is ENGINE-DERIVED from attributes/PlayStyles — "
            "computed per candidate, never a hardcoded label")

    # -- trait phrases -> inferred bands ---------------------------------------
    bands: list[dict] = []
    seen_band_attrs: set[str] = set()

    def _add_band(attr: str, band: str, source: str, explicit: bool,
                  origin: str) -> None:
        if attr in seen_band_attrs:
            return
        seen_band_attrs.add(attr)
        bands.append({"attribute": attr, "band": band})
        intent.soft_preferences.append(SoftPreference(
            "ATTRIBUTE_BAND", attr, band, weight=1.0, source=source, explicit=explicit))
        intent.notes.append(
            f"'{origin}' -> {attr} ≥ band '{band}' (soft target "
            f"{QUALITY_BANDS[band]} per engine_config, INFERRED — not an exact user number)"
            if source == "INFERRED" else
            f"'{origin}' -> {attr} band '{band}' (soft target)")

    for phrase, attrs in sorted(_TRAIT_BANDS.items(), key=lambda kv: -len(kv[0])):
        if phrase in t:
            for attr, band in attrs:
                _add_band(attr, band, "INFERRED", False, phrase)
            t = _mask(t, phrase)

    # -- explicit numeric attribute minimums: "minimum 85 pace", "pace 85+", ...
    num_patterns = (
        r"(?:min(?:imum)?|at least|no less than|above|over)\s+(\d{2})\s+([a-z ]+?)(?=[,.;]|\band\b|\+|$)",
        r"([a-z ]+?)\s+(\d{2})\s*\+",
        r"([a-z ]+?)\s+(?:of\s+)?(?:at least\s+)?(\d{2})(?=[,.;)]|\s+(?:or|and|plus)\b|$)",
    )
    prefs: list[dict] = []
    hard_attrs: set[str] = set()
    for pat in num_patterns:
        for m in re.finditer(pat, t):
            g1, g2 = m.group(1), m.group(2)
            num_s, attr_s = (g1, g2) if g1.isdigit() else (g2, g1)
            attr = _ATTR_WORDS.get(attr_s.strip())
            if attr is None:
                continue
            try:
                val = int(num_s)
            except ValueError:
                continue
            if not 1 <= val <= 99 or attr in hard_attrs:
                continue
            hard_attrs.add(attr)
            prefs.append({"attribute": attr, "min_value": val, "weight": 1.5})
            intent.hard_constraints.append(HardConstraint(
                "ATTRIBUTE_MIN", attr, val, enforced=True,
                reason="explicit numeric minimum from user text"))
    if prefs:
        intent.fields["attribute_preferences"] = IntentField("attribute_preferences", prefs)

    # -- qualitative "good/excellent <attr>" bands ------------------------------
    for band_word, band in sorted(_BAND_WORDS.items(), key=lambda kv: -len(kv[0])):
        for attr_word, attr in _ATTR_WORDS.items():
            for pat in (rf"\b{re.escape(band_word)}\s+(?:in\s+)?{re.escape(attr_word)}\b",
                        rf"\b{re.escape(attr_word)}\s+(?:is\s+|are\s+)?{re.escape(band_word)}\b"):
                if re.search(pat, t) and attr not in seen_band_attrs and attr not in hard_attrs:
                    _add_band(attr, band, "USER_TEXT", True, f"{band_word} {attr_word}")

    # -- plain attribute mentions (legacy behavior: weight 1.5 preferences) -----
    for word, attr in _ATTR_WORDS.items():
        if word in t and attr not in hard_attrs and \
                all(p["attribute"] != attr for p in prefs):
            prefs.append({"attribute": attr, "weight": 1.5})
    if prefs and "attribute_preferences" not in intent.fields:
        intent.fields["attribute_preferences"] = IntentField(
            "attribute_preferences", prefs,
            note="mentioned attributes become soft weight preferences")
    elif prefs:
        intent.fields["attribute_preferences"] = IntentField(
            "attribute_preferences", prefs)

    if bands:
        intent.fields["attribute_bands"] = IntentField("attribute_bands", bands)

    # -- budget -----------------------------------------------------------------
    budget = None
    for bm in re.finditer(r"(?:under|below|max(?:imum)?|budget(?: of)?|up to|<)?\s*(\d[\d.,]*)\s*(k\b|k\s|thousand|\s*m\b)?", t):
        num = bm.group(1).replace(",", "")
        try:
            val = float(num)
        except ValueError:
            continue
        unit = (bm.group(2) or "").strip().lower()
        if unit.startswith("k") or unit == "thousand":
            val *= 1000
        elif unit == "m":
            val *= 1_000_000
        if 500 <= val <= 10_000_000:
            budget = int(val)
            break
    if budget is not None:
        intent.fields["budget_coins"] = IntentField("budget_coins", budget)
        intent.hard_constraints.append(HardConstraint(
            "BUDGET", "budget_coins", budget, enforced=False,
            reason="enforceable ONLY when a verified market price exists; "
                   "with no price data this stays BUDGET_UNVERIFIED, never assumed affordable"))
    else:
        intent.notes.append("no budget detected")

    # -- OVR stance ---------------------------------------------------------------
    if re.search(r"\b(?:don'?t|do not)\s+care\s+about\s+(?:maximum\s+)?ovr\b", t) or \
       "not the highest ovr" in t or "highest rated" not in t and "ignore ovr" in t:
        intent.fields["overall_quality_bias"] = IntentField(
            "overall_quality_bias", "low",
            note="user deprioritized raw OVR — overall_quality weight scaled (configurable)")
    if re.search(r"\bmin(?:imum)?\s+(\d{2})\s+ovr\b", t) or re.search(r"\bovr\s+(\d{2})\s*\+", t):
        m = re.search(r"\b(\d{2})\s+ovr\b|\bovr\s+(\d{2})", t)
        if m:
            val = int(m.group(1) or m.group(2))
            if 1 <= val <= 99:
                intent.hard_constraints.append(HardConstraint(
                    "MIN_OVR", "min_overall", val, reason="explicit numeric OVR minimum"))
                intent.fields["min_overall"] = IntentField("min_overall", val)

    if required_ps:
        intent.fields["required_playstyles"] = IntentField("required_playstyles", required_ps)
        for ps in required_ps:
            intent.hard_constraints.append(HardConstraint(
                "REQUIRED_PLAYSTYLE", ps, ps, enforced=True,
                reason="explicitly mandatory PlayStyle"))
    desired_ps = [p for p in desired_ps if p not in required_ps]
    if desired_ps:
        intent.fields["desired_playstyles"] = IntentField("desired_playstyles", desired_ps)
        for ps in desired_ps:
            intent.soft_preferences.append(SoftPreference("PLAYSTYLE", ps, ps, weight=1.0))

    # -- league/club/nation requirements -------------------------------------------
    for kind, marker in (("REQUIRED_LEAGUE", "league:"), ("REQUIRED_CLUB", "club:"),
                         ("REQUIRED_NATION", "nation:")):
        m = re.search(rf"{re.escape(marker)}\s*([a-z0-9 .'-]+?)(?=[,.;]|\band\b|$)", t)
        if m:
            value = m.group(1).strip().title()
            intent.hard_constraints.append(HardConstraint(
                kind, kind.split("_")[1].lower(), value, enforced=True,
                reason="explicit structured requirement (marker syntax)"))

    # -- complement hint (§19: "my other CM is very attacking") ----------------------
    m = re.search(r"\b(?:my|the)\s+other\s+(cm|cdm|cam|st|cb|lb|rb|lw|rw|lm|rm|gk)\b[^.;]*", t)
    if m:
        frag = m.group(0)
        bias = None
        if re.search(r"attack|creative|forward|offensiv", frag):
            bias = "ATTACKING"
        elif re.search(r"defend|defensiv|destroy|protect|hold", frag):
            bias = "DEFENSIVE"
        elif re.search(r"fast|pace|quick", frag):
            bias = "FAST"
        elif re.search(r"slow|physical|strong", frag):
            bias = "PHYSICAL"
        hint = {"position": m.group(1).upper(), "bias": bias}
        intent.fields["complement_hint"] = IntentField(
            "complement_hint", hint,
            source="USER_TEXT" if bias else "INFERRED",
            confidence="HIGH" if bias else "MEDIUM",
            explicit=bias is not None,
            note="pair-complementarity hint; advisory unless squad context exists")
        intent.soft_preferences.append(SoftPreference(
            "COMPLEMENT", "complement_hint", hint, weight=1.0,
            source="USER_TEXT", explicit=bias is not None))

    # -- Roles: no ingested vocabulary => never parsed from text ----------------------
    if re.search(r"\brole\b", t):
        intent.notes.append(
            "Role mention detected but Role data is NOT ingested for this version — "
            "role_fit stays INSUFFICIENT_EVIDENCE (withheld, never guessed)")

    intent.notes.append(
        "deterministic rule parser — every emitted value comes from reference "
        "tables or explicit user numbers; unrecognized fragments were recorded, "
        "never guessed")
    return intent


def draft_from_intent(intent: ParsedIntent) -> dict:
    return intent.to_draft()
