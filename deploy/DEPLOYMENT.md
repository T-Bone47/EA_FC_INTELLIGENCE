# Deployment Guide — EA FC Player Intelligence

Target stack: Python 3.13, FastAPI + gunicorn/uvicorn, PostgreSQL 17, built React SPA
served same-origin by the API. Everything below is reproducible from a clean machine.

## 0. What gets deployed

| Component | Artifact | Notes |
|---|---|---|
| API + SPA | `backend/` + `frontend/dist` | one uvicorn/gunicorn app; SPA mounted when `FRONTEND_DIST` is set |
| Database | PostgreSQL 17 | schema from `db/DATABASE_SCHEMA_V1.sql` + `db/migrations/*.sql` + `db/seed_reference_data.sql` |
| Data | `scripts/ingest_*.py` | idempotent; re-runnable on every deploy |

No background workers, no cache server, no message queue — deliberately minimal.

## 1. Provision (bare metal / VM)

```bash
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-venv postgresql-17 nodejs npm   # node only needed to BUILD the frontend
sudo -u postgres psql -c "CREATE ROLE eafc LOGIN PASSWORD '<strong-password>' CREATEDB"
```

## 2. Configure

```bash
sudo mkdir -p /opt/eafc && sudo chown $USER /opt/eafc
cp -r ea_fc_player_intelligence /opt/eafc/
cp deploy/.env.example /opt/eafc/eafc.env
# edit /opt/eafc/eafc.env:
#   DATABASE_URL   -> real credentials
#   JWT_SECRET     -> python3 -c "import secrets; print(secrets.token_hex(32))"
#   ENVIRONMENT    -> production   (the app REFUSES to boot in production without JWT_SECRET)
#   CORS_ORIGINS   -> leave empty for same-origin; otherwise exact https origins
chmod 600 /opt/eafc/eafc.env
```

## 3. Database schema + seed

```bash
cd /opt/eafc/ea_fc_player_intelligence
python3 -m venv /opt/eafc/venv && /opt/eafc/venv/bin/pip install -r backend/requirements.txt gunicorn
set -a; . /opt/eafc/eafc.env; set +a
python3 scripts/setup_database.py        # idempotent; applies schema + migrations + seed, tracks checksums
```

`setup_database.py` records every file in `schema_migrations` with a checksum;
re-running is a no-op unless a migration changed (changed checksums fail loudly
instead of half-applying — inspect before forcing).

## 4. Ingest production data (idempotent)

```bash
python3 scripts/ingest_fc26_foundation.py    # 16,228 players from the CC0 Kaggle carrier dataset
python3 scripts/ingest_real_identities.py    # 20 real-player identity links
# synthetic fixture cards are TEST-ONLY; do NOT run ingest_synthetic_cards.py in production.
```

Every script is safe to re-run: upserts on natural keys, no duplicates, child rows
re-pointed at canonical ids. Legal gate: sources with `legal_gate=REQUIRED` and no
`cleared_by` are refused by the pipeline — this is intentional and must not be bypassed.

## 5. Build the frontend

```bash
cd frontend && npm ci && npm run build     # emits frontend/dist (tsc --noEmit runs first)
npm run test                               # vitest unit suite must pass
```

Point `FRONTEND_DIST` at the absolute path of `frontend/dist`. The API then serves
`/` (SPA fallback) and `/assets/*` (hashed, immutable) on the same origin as `/api/*`.

## 6. Run

systemd (recommended): see `deploy/eafc-api.service`.

```bash
sudo cp deploy/eafc-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eafc-api
journalctl -u eafc-api -f
```

Docker alternative: `deploy/docker-compose.yml` (multi-stage build includes the SPA).

Manual smoke after start:

```bash
curl -fsS http://127.0.0.1:8000/api/health          # {"status":"ok",...}
curl -fsS http://127.0.0.1:8000/api/health/ready    # real counts; 503 when DB is down
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/          # 200 (SPA)
curl -s -X POST http://127.0.0.1:8000/api/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"game_version":"FC26","position":"CM","limit":3}' | head -c 300
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/recommendations \
  -H 'Content-Type: application/json' -d '{"game_version":"FC27","position":"CM"}'   # 404 — honest NO_DATA
```

## 7. Reverse proxy / TLS

See `deploy/nginx.conf.example`. Terminate TLS at nginx; the app adds HSTS itself
when `ENVIRONMENT=production`. Keep `client_max_body_size` aligned with
`MAX_REQUEST_BYTES`.

## 8. Operations

- **Health**: `/api/health` (liveness, no DB) and `/api/health/ready` (readiness,
  real per-version counts). Alert on ready != 200 for > 1 min.
- **Request tracing**: every response carries `X-Request-ID`; 500s return ONLY
  `detail` + `request_id` — grep the service journal for the id to see the traceback.
- **Rate limits**: in-memory per-IP sliding windows (auth 10/min, general 240/min).
  Single-instance by design; if you scale horizontally, move `RateLimiter` to Redis
  before running >1 replica, or limits become per-node.
- **Backups**: `pg_dump eafc_intelligence` nightly is sufficient — all derived data
  can be rebuilt from `data/` + ingest scripts; user tables (profiles, squads,
  saved, feedback) exist only in the DB, so backups are REQUIRED for those.
- **Upgrades**: pull code → `pip install -r backend/requirements.txt` →
  `setup_database.py` (applies new migrations) → re-run ingest scripts if new data
  files shipped → `npm ci && npm run build` → `systemctl restart eafc-api`.
  The API is stateless except the rate-limit window (resets on restart — fine).

## 9. FC27 readiness (what happens when real FC27 data exists)

1. Register an authorized source in `source_registry` (`legal_gate` cleared).
2. Write an adapter producing the same normalized row shape (see
   `backend/ingestion/adapter.py`, `local_file_adapter.py` for the pattern).
3. Ingest with `game_version=FC27` — the pipeline enforces: no mixed-version rows,
   provenance on every record, synthetic data rejected.
4. Flip `game_version.status` to ACTIVE via migration.
   The API, engine and UI switch on automatically; FC26 behaviour is untouched.

Until then every FC27 request returns an explicit `NO_DATA` 404 — never FC26 data
under an FC27 label, never fabricated records.

## 10. Security checklist (verified by `backend/tests/test_security.py`)

- [x] bcrypt password hashing; no plaintext anywhere in responses
- [x] server-side revocable JWT sessions (logout / logout-all)
- [x] generic login errors (no user enumeration)
- [x] rate limiting on auth + general routes, `Retry-After` on 429
- [x] security headers on every response; HSTS in production
- [x] request size cap (413)
- [x] 500s leak nothing but a request id
- [x] CORS closed by default
- [x] SQL injection attempts inert (parameterized everywhere; verified against live DB)
- [x] ownership enforced on squads/saved/feedback (other users get 404, not 403)
- [x] synthetic data firewalled from every production read path
