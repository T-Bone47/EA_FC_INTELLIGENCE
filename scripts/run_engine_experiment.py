#!/usr/bin/env python3
"""Run an offline engine experiment (§48) against the evaluation suite.

NEVER touches production configuration — variants live only inside this
process and in the `experiment`/`experiment_result` tables.

Examples:
  python3 scripts/run_engine_experiment.py --list
  python3 scripts/run_engine_experiment.py \\
      --name exp-attr-boost --hypothesis "attribute_fit 0.35 vs tactical 0.10" \\
      --weights attribute_fit=0.35 tactical_fit=0.10
  python3 scripts/run_engine_experiment.py --name exp-floor-045 --tactical-floor 0.45
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="list scenarios and exit")
    ap.add_argument("--name", help="experiment name (unique)")
    ap.add_argument("--hypothesis", default="", help="what the variant is testing")
    ap.add_argument("--weights", nargs="*", default=[],
                    help="component weight overrides as key=value pairs "
                         "(full set required, must sum to 1.0)")
    ap.add_argument("--tactical-floor", type=float, default=None)
    ap.add_argument("--scenarios", nargs="*", default=None)
    ap.add_argument("--no-persist", action="store_true")
    args = ap.parse_args()

    from backend.services import engine_evaluation
    if args.list:
        for name, fn in sorted(engine_evaluation.SCENARIOS.items()):
            print(f"{name:28s} {fn()['expect']}")
        return 0

    if not args.name:
        ap.error("--name is required (or use --list)")

    from backend.services.scoring_config import COMPONENT_WEIGHTS
    overrides: dict = {}
    if args.weights:
        cw = dict(COMPONENT_WEIGHTS)
        for pair in args.weights:
            k, _, v = pair.partition("=")
            if k not in cw:
                ap.error(f"unknown component {k!r}")
            cw[k] = float(v)
        overrides["component_weights"] = cw
    if args.tactical_floor is not None:
        overrides["tactical_floor"] = args.tactical_floor
    if not overrides:
        ap.error("nothing to experiment with: pass --weights and/or --tactical-floor")

    from backend.services.engine_experiments import run_experiment
    summary = run_experiment(args.name, args.hypothesis, overrides,
                             scenario_names=args.scenarios,
                             persist=not args.no_persist)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_scenario"},
                     indent=2))
    changed = [s for s, d in summary["per_scenario"].items() if d["winner_changed"]]
    print("\nwinner changes:", changed or "none")
    for s in changed:
        d = summary["per_scenario"][s]
        print(f"  {s}: {d['baseline']['best']} -> {d['variant']['best']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
