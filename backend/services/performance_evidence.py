"""Versioned evidence types and conservative descriptive evaluation for the FC27 lab."""
from collections import Counter, defaultdict
from csv import DictReader
from datetime import date
from functools import lru_cache
from pathlib import Path
import re
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from backend.services.fc27_card_research import digest
from backend.services.formations import FORMATION_SLOTS, find_slot
from backend.services.scoring_config import POSITION_ATTRIBUTE_WEIGHTS, TACTICAL_ATTRIBUTE_WEIGHTS


Kind = Literal[
    "OFFICIAL_GAME_MECHANIC", "OFFICIAL_CARD_ATTRIBUTE", "COMMUNITY_OPINION", "CREATOR_OBSERVATION",
    "OWNER_RECORDED_MATCH", "USER_SUBMITTED_MATCH", "CONTROLLED_EXPERIMENT", "MODEL_PREDICTION", "UNVERIFIED_CLAIM",
]
Metric = Literal["goals", "assists", "shots", "shots_on_target", "passes_completed", "passes_attempted",
                 "tackles_won", "interceptions", "saves", "shots_faced"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[\w.:-]+$")]
Patch = Annotated[str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+(?:\.[0-9]+){0,2}$", max_length=20)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
MatchKind = {"OWNER_RECORDED_MATCH", "USER_SUBMITTED_MATCH", "CONTROLLED_EXPERIMENT"}
OpinionKind = {"COMMUNITY_OPINION", "CREATOR_OBSERVATION"}


@lru_cache(maxsize=1)
def sources():
    path = Path(__file__).resolve().parents[2] / "artifacts/phase31/RESEARCH_SOURCE_LEDGER.csv"
    with path.open(encoding="utf-8", newline="") as file:
        return {row["source_key"]: row for row in DictReader(file)}


@lru_cache(maxsize=1)
def official_rating_checks():
    path = Path(__file__).resolve().parents[2] / "artifacts/phase31/CARD_ATTRIBUTE_REFERENCES.csv"
    with path.open(encoding="utf-8", newline="") as file:
        return {row["source_item_id"]: row for row in DictReader(file)}


def normalize_text(value):
    return " ".join(re.findall(r"[\w]+", value.casefold()))


def canonical_citation(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.port not in (None, 443)
            or any(char.isspace() for char in url) or "\\" in url or "." not in parsed.hostname):
        raise ValueError("Use an HTTPS source permalink without credentials")
    host = parsed.hostname.lower()
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in {"si", "fbclid", "gclid", "feature"}]
    path = parsed.path.rstrip("/") or "/"
    if host in {"www.youtube.com", "m.youtube.com", "youtube.com"} and path == "/watch":
        query = [(key, value) for key, value in query if key == "v"]
        host = "www.youtube.com"
    if host == "youtu.be" and re.fullmatch(r"/[\w-]{11}", path):
        host, path, query = "www.youtube.com", "/watch", [("v", path[1:])]
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


class Context(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_patch: Patch | None = None
    formation: Label | None = None
    slot: Label | None = None
    position: Label | None = None
    role: Label | None = None
    tactical_profile: Label | None = None
    game_mode: Label | None = None
    controller: Literal["HUMAN", "AI", "MIXED"] | None = None

    @model_validator(mode="after")
    def check_context(self):
        if self.formation and self.formation not in FORMATION_SLOTS:
            raise ValueError("Unknown formation")
        if self.position and self.position not in POSITION_ATTRIBUTE_WEIGHTS:
            raise ValueError("Unknown position")
        if self.slot:
            formation_slot = find_slot(self.formation, self.slot)
            if not formation_slot or formation_slot.position != self.position:
                raise ValueError("Select the position that belongs to this formation slot")
        if self.tactical_profile and self.tactical_profile not in TACTICAL_ATTRIBUTE_WEIGHTS:
            raise ValueError("Unknown tactical profile")
        for field in ("role", "game_mode"):
            value = getattr(self, field)
            if value:
                setattr(self, field, " ".join(value.casefold().split()))
        return self


class Match(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_date: date
    match_key: Code
    minutes: int | None = Field(default=None, ge=1, le=120, strict=True)
    platform: Label | None = None
    opponent_context: Label | None = None
    skill_context: Label | None = None
    session_key: Code | None = None
    setup_key: Code | None = None
    protocol_key: Code | None = None
    block_key: Code | None = None
    order: Literal[1, 2] | None = None
    metrics: dict[Metric, Annotated[int, Field(ge=0, le=1000, strict=True)] | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_match(self):
        self.match_key = self.match_key.casefold()
        if self.match_date > date.today():
            raise ValueError("Match date cannot be in the future")
        for numerator, denominator in (("goals", "shots_on_target"), ("shots_on_target", "shots"),
                                       ("passes_completed", "passes_attempted"), ("saves", "shots_faced")):
            first, second = self.metrics.get(numerator), self.metrics.get(denominator)
            if first is not None and second is not None and first > second:
                raise ValueError(f"{numerator} cannot exceed {denominator}")
        return self


class EvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    game_version: Literal["FC27"]
    card_item_id: UUID
    observation_type: Kind
    source_key: Code
    source_url: Annotated[str, StringConstraints(max_length=800)] | None = None
    source_date: date | None = None
    source_author: Label | None = None
    evidence_locator: Label | None = None
    context: Context
    topic: Code | None = None
    stance: Literal["SUPPORTS", "CONTRADICTS"] | None = None
    note: Note | None = None
    match: Match | None = None
    rights_attested: Literal[True]
    share_for_research: bool = False

    @model_validator(mode="after")
    def check_evidence(self):
        source = sources().get(self.source_key)
        if (not source or self.observation_type != source["observation_type"]
                or source["access"] not in {"REFERENCE_ONLY", "PERMITTED_SUBMISSION"}):
            raise ValueError("Select a registered and permitted intake source")
        if self.source_date and self.source_date > date.today():
            raise ValueError("Source date cannot be in the future")
        if self.source_url:
            self.source_url = canonical_citation(self.source_url)
            if source["source_url"] and urlsplit(self.source_url).hostname != urlsplit(source["source_url"]).hostname:
                raise ValueError("Citation host must match the registered source")
        if self.observation_type in MatchKind:
            if not self.match or self.topic or self.stance:
                raise ValueError("Match submissions require a match record and no claim stance")
        elif self.match or not self.note or not self.topic or not self.source_url:
            raise ValueError("Research notes require a topic, original citation and your own paraphrase")
        if self.observation_type in OpinionKind and (not self.source_author or not self.stance):
            raise ValueError("Opinion notes require an original author and stance")
        if self.observation_type == "CONTROLLED_EXPERIMENT":
            design = self.match
            if not all((design.minutes, design.platform, design.opponent_context, design.skill_context,
                        design.session_key, design.protocol_key, design.block_key, design.setup_key,
                        design.order, self.evidence_locator, self.context.game_patch, self.context.game_mode,
                        self.context.formation, self.context.slot, self.context.position, self.context.role,
                        self.context.controller, self.context.tactical_profile)):
                raise ValueError("Controlled reports require all matching fields and an evidence locator")
        return self

    def fingerprint(self):
        if self.match:
            return digest([str(self.card_item_id), self.match.match_key.casefold()])
        return digest([str(self.card_item_id), self.context.model_dump(), self.source_url,
                       self.topic.casefold(), self.stance, normalize_text(self.note)])


def patch_status(patch, target):
    if patch is None:
        return "PATCH_UNKNOWN"
    if target is None:
        return "FILTER_NOT_SET"
    return "EXACT_MATCH" if target == patch else "OTHER_PATCH"


def opinion_summary(rows):
    """A count of independent reviewed source families for each exact claim context."""
    groups = defaultdict(list)
    for row in rows:
        if row["evidence_kind"] not in OpinionKind:
            continue
        data = row["payload"]
        key = (str(row["card_item_id"]), data["topic"].casefold(), digest(data["context"]))
        groups[key].append(row)
    output = []
    for (item, topic, _), claims in sorted(groups.items()):
        # Printed mirrors and repeat reports cannot add independent votes.
        families, copies = defaultdict(set), set()
        for row in sorted(claims, key=lambda r: (r["source_key"], r["payload"]["source_url"], str(r["id"]))):
            data = row["payload"]
            source = sources()[row["source_key"]]
            copy = data["stance"], normalize_text(data["note"])
            if copy in copies:
                continue
            copies.add(copy)
            families[source["origin"]].add(data["stance"])
        support = sum(v == {"SUPPORTS"} for v in families.values())
        contradict = sum(v == {"CONTRADICTS"} for v in families.values())
        stances = set().union(*families.values())
        status = ("CONFLICTING" if len(stances) > 1 else "MULTIPLE_SOURCES_AGREE" if max(support, contradict) >= 3
                  else "LIMITED_OPINION")
        output.append({"card_item_id": item, "topic": topic, "status": status,
                       "supporting_origins": support, "contradicting_origins": contradict,
                       "context": claims[0]["payload"]["context"], "records": len(claims)})
    return output


def reported_matches(rows):
    """One observation per item and match key. Disputed values do not enter summaries."""
    groups = defaultdict(list)
    for row in rows:
        report = row["payload"].get("match")
        if report is not None:
            groups[(str(row["card_item_id"]), report["match_key"].casefold())].append(row)
    observations, conflicts = [], []
    for (item, _), group in sorted(groups.items()):
        variants = {digest([row["payload"]["match"], row["payload"]["context"]]) for row in group}
        if len(variants) == 1:
            observations.append(sorted(group, key=lambda row: (row["evidence_kind"] != "CONTROLLED_EXPERIMENT", str(row["id"])))[0])
        else:
            conflicts.append({"card_item_id": item, "observations": len(group), "status": "CONFLICTING_MATCH_REPORTS"})
    return observations, conflicts


def compare_observed(rows, cards, metric, context):
    """Counterbalanced complete pairs, matched within the same reporter and session."""
    observations, conflicts = reported_matches(rows)
    blocks = defaultdict(list)
    for row in observations:
        data = row["payload"]
        if (row["evidence_kind"] != "CONTROLLED_EXPERIMENT" or str(row["card_item_id"]) not in cards
                or data["context"] != context or not context["game_patch"] or data["match"]["metrics"].get(metric) is None):
            continue
        match = data["match"]
        key = (str(row["owner_id"]), match["protocol_key"], match["session_key"], match["block_key"])
        blocks[key].append(row)
    pairs = []
    for key, block in sorted(blocks.items()):
        by_card = {str(row["card_item_id"]): row for row in block}
        if len(block) != 2 or set(by_card) != set(cards):
            continue
        left, right = [by_card[card]["payload"]["match"] for card in cards]
        fields = ("match_date", "minutes", "platform", "opponent_context", "skill_context", "setup_key")
        if (any(left[field] != right[field] for field in fields) or left["order"] == right["order"]
                or left["match_key"].casefold() == right["match_key"].casefold()):
            continue
        stratum = (key[1], left["platform"], left["opponent_context"], left["skill_context"], left["setup_key"])
        pairs.append((key[:3], left["order"], left["metrics"][metric], right["metrics"][metric], left["minutes"], stratum))
    counts = Counter(pair[1] for pair in pairs)
    strata = {pair[5] for pair in pairs}
    evidence = {"complete_pairs": len(pairs), "first_card_first": counts[1], "second_card_first": counts[2],
                "disputed_match_reports": len(conflicts), "independent_sessions": len({pair[0] for pair in pairs}),
                "metric": metric, "matching_strata": len(strata), "observed_per_90": None, "paired_difference_per_90": None,
                "status": "INSUFFICIENT_GAMEPLAY_EVIDENCE"}
    # Require counterbalancing and more than one recorded session before comparing.
    if len(strata) == 1 and counts[1] and counts[2] and evidence["independent_sessions"] >= 2:
        totals = [sum(pair[index] for pair in pairs) for index in (2, 3)]
        minutes = sum(pair[4] for pair in pairs)
        rates = [round(90 * total / minutes, 6) for total in totals]
        evidence.update(status="DESCRIPTIVE_PAIRED_RESULTS", observed_per_90=dict(zip(cards, rates)),
                        paired_difference_per_90=round(90 * (totals[0] - totals[1]) / minutes, 6))
    return evidence
