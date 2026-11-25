"""Evaluate the private FC27 striker pilot from a filled match sheet."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

from backend.services.fc27_card_research import digest
from backend.services.performance_evidence import Context, Match, compare_observed
from verification.prepare_fc27_striker_pilot import OUT, PILOT, schedule

FIXED = ("protocol_key", "session_key", "block_key", "order", "tactical_profile", "card",
         "name", "source_item_id", "card_item_id", "formation", "slot", "position", "controller")
CONTEXT = ("game_patch", "formation", "slot", "position", "role", "tactical_profile",
           "game_mode", "controller")
SETUP = ("platform", "opponent_context", "skill_context", "setup_key")
MATCH = ("match_date", "match_key", "session_key", "protocol_key", "block_key", *SETUP)
METRICS = ("tackles_won", "interceptions", "shots", "shots_on_target", "goals")
OBSERVATION = ("match_date", "minutes", "evidence_locator", *METRICS)


def load_predictions(path):
    report = json.loads(path.read_text(encoding="utf-8"))
    checksum = report.pop("prediction_sha256")
    if report["protocol_key"] != PILOT or checksum != digest(report):
        raise ValueError("Use the original frozen predictions for this pilot")
    return {**report, "prediction_sha256": checksum}


def read_sheet(path, predictions):
    planned = {r["match_key"]: r for r in schedule(predictions)}
    slots = {(r["block_key"], str(r["order"])): r for r in planned.values()}
    seen, excluded = set(), set()
    replacements, groups = defaultdict(list), defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        expected = set(next(iter(planned.values())))
        if not reader.fieldnames or len(reader.fieldnames) != len(expected) or set(reader.fieldnames) != expected:
            raise ValueError("Use the pilot match sheet headers")
        for line, raw in enumerate(reader, start=2):
            if None in raw or None in raw.values():
                raise ValueError(f"Row {line} has the wrong number of columns")
            row = {key: value.strip() for key, value in raw.items()}
            key = row["match_key"].casefold()
            slot = slots.get((row["block_key"], row["order"]))
            if key in seen or not slot or any(row[field] != str(slot[field]) for field in FIXED):
                raise ValueError(f"Row {line} duplicates a match key or changes the frozen schedule")
            seen.add(key)
            if row["deviation"]:
                if key in planned:
                    excluded.add(key)
                continue
            if not any(row[field] for field in OBSERVATION):
                continue
            try:
                if not all(row[field] for field in (*CONTEXT, *MATCH, "minutes", "evidence_locator")):
                    raise ValueError("complete the setup, patch, minutes and evidence locator for played rows")
                context = Context(**{field: row[field] for field in CONTEXT}).model_dump(mode="json")
                match = Match(**{field: row[field] for field in MATCH}, order=int(row["order"]),
                              minutes=int(row["minutes"]),
                              metrics={field: int(row[field]) if row[field] else None for field in METRICS})
            except ValueError as exc:
                raise ValueError(f"Row {line}: {exc}") from exc
            if key not in planned:
                replacements[row["block_key"]].append(row["order"])
            scope = tuple(context[field] for field in CONTEXT) + tuple(row[field] for field in SETUP)
            groups[scope].append({"id": key, "owner_id": "local-pilot", "card_item_id": row["card_item_id"],
                                  "evidence_kind": "CONTROLLED_EXPERIMENT",
                                  "payload": {"match": match.model_dump(mode="json"), "context": context}})
    if not planned.keys() <= seen:
        raise ValueError("Keep all eight original schedule rows, including any excluded rows")
    for block, orders in replacements.items():
        originals = {key for key, row in planned.items() if row["block_key"] == block}
        if not originals <= excluded or sorted(orders) != ["1", "2"]:
            raise ValueError(f"Block {block} requires both original rows marked as deviations and one replacement pair")
    return groups, len(excluded)


def per_session(rows, cards, metric, context):
    sessions = defaultdict(list)
    for row in rows:
        sessions[row["payload"]["match"]["session_key"]].append(row)
    outcomes = {}
    for key, session in sorted(sessions.items()):
        if compare_observed(session, cards, metric, context)["complete_pairs"] != 1:
            continue
        by_card = {row["card_item_id"]: row["payload"]["match"] for row in session}
        a, b = (by_card[card] for card in cards)
        delta = 90 * (a["metrics"][metric] - b["metrics"][metric]) / a["minutes"]
        outcomes[key] = {"direction": "A" if delta > 0 else "B" if delta < 0 else None,
                         "a_minus_b_per_90": round(delta, 6)}
    return outcomes


def evaluate(sheet, predictions):
    cards = [predictions["cards"][arm]["card_item_id"] for arm in ("A", "B")]
    groups, excluded = read_sheet(sheet, predictions)
    tactics = {}
    for profile, prediction in predictions["tactics"].items():
        metric = prediction["primary_outcome_per_90"]
        leader = prediction["predictions"][0]["card"]
        strata = []
        for scope, rows in sorted(groups.items()):
            context = rows[0]["payload"]["context"]
            if context["tactical_profile"] != profile:
                continue
            evidence = compare_observed(rows, cards, metric, context)
            delta = evidence["paired_difference_per_90"]
            direction = None if delta in (None, 0) else "A" if delta > 0 else "B"
            agreement = None if delta is None else "TIED" if delta == 0 else (
                "AGREES" if direction == leader else "DISAGREES")
            strata.append({"context": context, "setup": dict(zip(SETUP, scope[-len(SETUP):])),
                           "rows": len(rows), "evidence": evidence, "direction": direction,
                           "prediction_agreement": agreement, "sessions": per_session(rows, cards, metric, context)})
        complete = any(s["evidence"]["status"] == "DESCRIPTIVE_PAIRED_RESULTS" for s in strata)
        tactics[profile] = {"metric": metric, "predicted_leader": leader, "strata": strata,
                            "status": ("DESCRIPTIVE_PAIRED_RESULTS" if complete
                                       else "INSUFFICIENT_GAMEPLAY_EVIDENCE")}
    return {"protocol_key": predictions["protocol_key"], "prediction_sha256": predictions["prediction_sha256"],
            "evidence_status": "LOCAL_UNREVIEWED_MATCH_SHEET", "played_rows": sum(map(len, groups.values())),
            "excluded_original_rows": excluded, "tactics": tactics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("--predictions", type=Path, default=OUT / "FROZEN_PREDICTIONS.json")
    args = parser.parse_args()
    try:
        result = evaluate(args.sheet, load_predictions(args.predictions))
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
