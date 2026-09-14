#!/usr/bin/env python3
"""
Deterministic database setup: create schema + apply migrations in order + seed
reference data. Idempotent; tracks applied files in schema_migrations.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/db python3 scripts/setup_database.py [--reset]

--reset drops and recreates the target database (DESTRUCTIVE — dev only).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "db"

DEFAULT_URL = "postgresql://eafc:eafc_dev_only@localhost:5432/eafc_intelligence"


def ordered_files() -> list[Path]:
    files = [DB_DIR / "DATABASE_SCHEMA_V1.sql"]
    files += sorted((DB_DIR / "migrations").glob("*.sql"))
    files += [DB_DIR / "seed_reference_data.sql"]
    return files


def ensure_database(url: str, reset: bool) -> None:
    import re
    m = re.match(r"postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)", url)
    if not m:
        raise SystemExit(f"Cannot parse DATABASE_URL: {url}")
    user, pw, host, port, dbname = m.group(1), m.group(2), m.group(3), m.group(4) or "5432", m.group(5)
    admin = f"postgresql://{user}:{pw}@{host}:{port}/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,)).fetchone()
        if reset and exists:
            print(f"RESET: dropping database {dbname}")
            conn.execute(
                f'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s', (dbname,))
            conn.execute(f'DROP DATABASE "{dbname}"')
            exists = None
        if not exists:
            print(f"Creating database {dbname}")
            conn.execute(f'CREATE DATABASE "{dbname}"')


def apply_all(url: str) -> None:
    with psycopg.connect(url) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        conn.commit()
        import hashlib
        for f in ordered_files():
            sql = f.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()[:16]
            row = conn.execute(
                "SELECT checksum FROM schema_migrations WHERE filename=%s", (f.name,)).fetchone()
            if row and row[0] == checksum:
                print(f"  skip (applied): {f.name}")
                continue
            if row and row[0] != checksum:
                print(f"  re-apply (changed): {f.name}")
            print(f"  applying: {f.name}")
            conn.execute(sql)
            conn.execute(
                """INSERT INTO schema_migrations (filename, checksum) VALUES (%s,%s)
                   ON CONFLICT (filename) DO UPDATE SET checksum=EXCLUDED.checksum,
                   applied_at=now()""", (f.name, checksum))
            conn.commit()
    print("Database setup complete.")


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    reset = "--reset" in sys.argv
    ensure_database(url, reset)
    apply_all(url)
