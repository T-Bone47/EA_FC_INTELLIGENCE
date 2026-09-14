"""Database connection pool management (psycopg3)."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.core.config import get_settings

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ConnectionPool(
                conninfo=get_settings().database_url,
                min_size=1,
                max_size=8,
                kwargs={"row_factory": dict_row},
                open=True,
            )
        return _pool


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with get_pool().connection() as conn:
        yield conn


def query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None
