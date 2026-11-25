"""Run private acceptance against a preprovisioned, disposable local QA database and built app."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api",required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    pg=urlsplit(os.environ["DATABASE_URL"])
    base=urlsplit(args.api)
    if (pg.hostname!="127.0.0.1" or pg.path!="/eafc_ci" or base.hostname!="127.0.0.1"
            or os.environ.get("ENVIRONMENT")!="test" or os.environ.get("FC27_CARD_RESEARCH_ENABLED","").lower()!="true"):
        raise SystemExit("Use the opted-in disposable eafc_ci loopback test environment.")
    args.out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,E2E_API_URL=args.api)
    # Fail on a missing pinned research release even if a portable pytest test would skip it.
    with build_opener(ProxyHandler({})).open(args.api+"/api/research/fc27/cards?include_research_data=true") as response:
        data=json.load(response)
        assert data["dataset"]=="fc27-card-items-local-r1" and data["total"]==9962
    for command in [
        [sys.executable,"-m","pytest","-q","backend/tests/test_phase30_card_lab.py","backend/tests/test_zero_budget_research.py",
         "--basetemp",str(Path(tempfile.mkdtemp(dir=args.out))/"pytest")],
        [sys.executable,"verification/check_local_card_release.py",args.api,str(args.out/"CARD_CHECKS.json")],
        ["node","frontend/verification/fc27-local.mjs"],
    ]:
        subprocess.run(command,cwd=ROOT,env=env,check=True)


if __name__=="__main__":
    main()
