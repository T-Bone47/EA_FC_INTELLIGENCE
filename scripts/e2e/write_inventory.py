import ast, os, re, sys, glob, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psycopg
from backend.api.main import app
spec = app.openapi()["paths"]
routes = [(m.upper(), p, op.get("summary") or op.get("operationId", ""), "bearer" if op.get("security") else "-") for p, ops in sorted(spec.items()) for m, op in ops.items() if m in ("get", "post", "put", "patch", "delete")]
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    cur = c.cursor(); cur.execute("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"); tabs = [t for (t,) in cur.fetchall()]
    cnt = {}
    for t in tabs: cur.execute(f'select count(*) from "{t}"'); cnt[t] = cur.fetchone()[0]
    cur.execute("select tgname, tgrelid::regclass::text from pg_trigger where not tgisinternal order by 2,1"); trig = cur.fetchall()
def doc1(f):
    try: d = ast.get_docstring(ast.parse(Path(f).read_text(encoding="utf-8"))) or ""
    except SyntaxError: d = ""
    return d.strip().splitlines()[0][:110] if d.strip() else "(no module docstring)"
mods = "\n".join(f"| `{Path(f).name}` | {doc1(f)} |" for f in sorted(glob.glob("backend/services/*.py")) if not f.endswith("__init__.py"))
tests = {}
for f in sorted(glob.glob("reports/e2e/evidence/baseline_chunks/test_*.txt")):
    if "CONTAMINATED" in f: continue
    m = re.findall(r"(\d+) (passed|failed|skipped)", open(f, encoding="utf-8", errors="replace").read().strip().splitlines()[-1]); tests[Path(f).stem] = " ".join(f"{n} {k}" for n, k in m)
trows = "\n".join(f"| `{k}` | {v} |" for k, v in tests.items())
rt = "\n".join(f"| {m} | `{p}` | {s} | {a} |" for m, p, s, a in routes)
keyc = {k: cnt[k] for k in ("game_player", "field_provenance", "fc27_card_identity", "ut_card", "card_price", "fc27_card_open_flag") if k in cnt}
md = f"""# Repository inventory (Phase 1)

Generated from the code, the OpenAPI schema and the live database by `scripts/e2e/write_inventory.py`; component statuses reflect only what was executed in this session.

## Actual v3 request-to-recommendation path
```
Browser (React SPA, /intelligence) --POST /api/v3/recommendations--> [nginx example in deploy/ — not exercised]
  -> FastAPI app (backend/api/main.py): CORS allow-list, request-id middleware, GZip(>=1 KB), unhandled-exception handler (logs request_id, returns 500)
  -> router backend/api/routes/recommendations.py  (pydantic RecommendationRequestV3: extra fields forbidden, limits)  [auth: optional]
  -> RecommendationServiceV3.recommend
       check_division -> _resolve (game version, RESEARCH_ONLY gate, reference distribution; FC27 never falls back to FC26)
       -> CandidateRepository.load_candidates   (SQL; cache key "version|synthetic|research"; TTL 120 s validated by a game_player watermark)
       -> RecommendationEngineV3.recommend
            eligibility gates -> demand composition (position + tactical blend) -> capability C_lo/C_hi (reference distribution, evidence interval)
            -> bounded modifiers (PlayStyle; interaction DISABLED) -> deterministic ranking -> ScoringContext per candidate
       -> explanation_service_v3 (derived from ScoringContext) -> v3_response_blocks (confidence, tactical_fit, evidence, near_tie, division)
       -> JSON response (+ eafc.v3.telemetry log record)
  <- gzip response  <- React renders the backend order (no sorting; tested)
```

## Components
| Component | Responsibility | Entry point | Tests in this baseline | Runtime verification (this session) | Known limitations |
|---|---|---|---|---|---|
| API application | routing, CORS, request id, gzip, error handler | `backend/api/main.py` | test_security*, test_v3_api_contract | exercised live (uvicorn) and via real browser | OpenAPI docs are served at `/api/docs` in dev; no CI |
| v3 routes | recommend / compare / what-if | `routes/recommendations.py` | test_v3_api_contract, test_recommendations_v3_api, test_phase23_version_wall_api | live + real-browser QA (34/34 checks) | no rate limiter on v3 routes (to be confirmed in Phase 8/9) |
| v2 routes | legacy recommend / compare / cards / squads | `routes/*.py` | test_integration_production etc. | partially | **still mounted**; 15 of the 24 baseline failures concern the v2 engine/features |
| Auth | register, login, JWT, sessions | `routes/auth.py`, `deps.py` | test_auth* | login throttling reproduced (10/min -> 429) | in-process limiter: per worker, not shared |
| RecommendationServiceV3 | orchestration, gates, response blocks, telemetry | `services/recommendation_service_v3.py` | v3 contract/api tests | live | - |
| Engine V3.2 | eligibility, demand, capability, modifiers, ranking, ScoringContext | `services/recommendation_engine_v3.py` (+ modules below) | test_engine_v3_*, test_v3_2_*, golden tests | executed; V3.2 lab NOT rerun in this session yet | GK model tactically inert (documented); interaction disabled |
| Versioned config | V3.1 frozen, V3.2 default | `services/v3_config.py` | test_v3_2_config | executed | - |
| Reference distributions | frozen per game version | `services/reference_distribution.py`, `data/reference_distributions/` | test_reference_*, version wall | rebuilt DB reproduced the frozen hashes earlier | FC27 distribution is research-only |
| CandidateRepository | candidate SQL + cache | `data_access/candidate_repository.py` | test_postgres_integration | executed | watermark covers only `game_player`; see Phase 7 |
| PostgreSQL | 51 tables, triggers (version wall, research firewall) | `db/*.sql`, `scripts/setup_database.py` | test_postgres_integration, test_fc27_card_identity_research | rebuilt from scratch this session | tests write to the shared dev DB |
| Ingestion | idempotent loaders + provenance builders | `scripts/ingest_*.py`, `build_*.py` | ingest tests | re-run this session (FC26 16,228; FC27 19,789; provenance 1,645,154) | - |
| FC27 card-identity layer | research-only isolated tables | migration 009, `scripts/ingest_fc27_card_identity.py` | test_fc27_card_identity_research (16) | ingested: 20,175 identities | `futgg` registry = NOT_PERMITTED; owner decision pending |
| Frontend | React SPA, `/intelligence` | `frontend/src` | vitest 82 + 3 live (skipped offline) | real Chromium QA 34/34, axe 0 violations in 3 states | no real-device or screen-reader testing |
| Intelligence lab | invariants + discrimination research | `services/intelligence_lab.py`, `scripts/run_intelligence_lab.py` | test_lab_resume | NOT rerun in this session | ~10 min; sandbox restarts interrupt it |
| Observability | loggers `eafc.api`, `eafc.v3.telemetry`; `X-Request-ID`; telemetry record | `main.py`, service | test_security (header) | read + exercised | no metrics endpoint; no tracing |
| Deployment | Dockerfile, docker-compose, systemd unit, nginx example | `deploy/` | none | **NOT exercised** | - |
| **Real-time propagation** | **NOT_IMPLEMENTED** | - | - | strict code search: no WebSocket/SSE/queue/scheduler/polling/background task | request/response only; see Phase 7 |

Database facts: {len(tabs)} base tables; key row counts {keyc}. Non-internal triggers: {len(trig)}.
Applied migrations: `db/migrations/*.sql` (002-009) on top of `DATABASE_SCHEMA_V1.sql`.

## API surface ({len(routes)} operations, from OpenAPI)
| Method | Path | Summary | Auth |
|---|---|---|---|
{rt}

## Engine/service modules (first docstring line)
| Module | Responsibility |
|---|---|
{mods}

## Test modules and baseline outcome
| Module | Outcome |
|---|---|
{trows}
"""
Path("reports/e2e/REPOSITORY_INVENTORY.md").write_text(md, encoding="utf-8"); print("inventory written:", len(md), "chars |", len(routes), "operations |", len(tabs), "tables")
