"""Facts for reports/e2e/REPOSITORY_INVENTORY.md come from live introspection, not from README files."""
import json, subprocess, sys, warnings, os
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psycopg
from backend.api.main import app
def walk(routes, prefix=""):
    out = []
    for r in routes:
        sub = getattr(r, "app", None)
        if sub is not None and hasattr(sub, "routes"): out += walk(sub.routes, prefix + getattr(r, "path", ""))
        elif getattr(r, "methods", None):
            deps = [getattr(d.call, "__name__", "?") for d in getattr(r, "dependant", None).dependencies] if getattr(r, "dependant", None) else []
            out += [(m, prefix + r.path, ",".join(x for x in deps if x != "?")) for m in sorted(r.methods) if m not in ("HEAD", "OPTIONS")]
    return out
rows = sorted(set(walk(app.routes)), key=lambda x: (x[1], x[0]))
groups = {}
for m, p, d in rows: groups.setdefault("/".join(p.split("/")[:3]) if p.count("/") > 2 else p, []).append((m, p, d))
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    cur = c.cursor(); cur.execute("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"); tables = [t for (t,) in cur.fetchall()]
    counts = {}
    for t in tables: cur.execute(f'select count(*) from "{t}"'); counts[t] = cur.fetchone()[0]
    cur.execute("select version()"); pg = cur.fetchone()[0].split(",")[0]
out = {"route_count": len(rows), "groups": {k: len(v) for k, v in groups.items()}, "routes": rows, "tables": counts, "pg": pg,
       "migrations": sorted(p.name for p in Path("db/migrations").glob("*.sql")),
       "engine_modules": sorted(p.name for p in Path("backend/services").glob("*.py") if p.name != "__init__.py"),
       "test_modules": len(list(Path("backend/tests").glob("test_*.py"))), "frontend_tests": len(list(Path("frontend/src").rglob("*.test.ts*")))}
Path("reports/e2e/_inventory_facts.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print("routes:", out["route_count"], out["groups"]); print("v3 routes:", [(m, p, d) for m, p, d in rows if "/v3/" in p]); print("tables:", len(tables), "| key counts:", {k: counts[k] for k in ("game_player", "field_provenance", "fc27_card_identity", "ut_card", "card_price") if k in counts})
print("migrations:", out["migrations"]); print("service modules:", len(out["engine_modules"])); print("test modules:", out["test_modules"], "| frontend test files:", out["frontend_tests"])
