"""
Evaluation log storage.

  DATABASE_URL set (Supabase Postgres)     -> PostgreSQL via psycopg 3 (persistent)
  otherwise                                -> SQLite file DB_PATH (local development)

On Render's free web service the filesystem is ephemeral, so SQLite data would be lost on every
restart, redeploy or spin-down: use DATABASE_URL there.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).resolve().parent / "karirfit.db"))
# FR10: administrator changes to the catalogue (careers, skills, interests, courses) on top of model.json.
# payload NULL = item deleted; no row = original item. Kept in the database so changes survive a restart.
CATALOG_DDL = ("CREATE TABLE IF NOT EXISTS catalog(kind TEXT NOT NULL, item_id TEXT NOT NULL, payload TEXT, ts REAL, "
               "PRIMARY KEY (kind, item_id))")


class Storage:
    def __init__(self):
        self.pg = DATABASE_URL.startswith(("postgres://", "postgresql://"))
        self.error = None
        if self.pg:
            try:
                import psycopg  # psycopg[binary]
                self._psycopg = psycopg
                self.url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
                with self._conn() as con:
                    con.execute("CREATE TABLE IF NOT EXISTS log(id SERIAL PRIMARY KEY, ts DOUBLE PRECISION, "
                                "kind TEXT, session TEXT, payload TEXT)")
                    con.execute(CATALOG_DDL.replace("REAL", "DOUBLE PRECISION"))
                    # Supabase exposes new public tables to the browser roles: lock them to the backend
                    con.execute("ALTER TABLE catalog ENABLE ROW LEVEL SECURITY")
                    try:
                        con.execute("REVOKE ALL ON catalog FROM anon, authenticated")
                    except Exception:   # plain PostgreSQL without Supabase roles
                        pass
                return
            except Exception as e:   # a wrong DATABASE_URL must not take the whole API down
                self.error = str(e)[:300]
                print("[storage] Postgres unavailable, falling back to SQLite:", self.error, flush=True)
                self.pg = False
        with self._conn() as con:
            con.execute("CREATE TABLE IF NOT EXISTS log(id INTEGER PRIMARY KEY, ts REAL, kind TEXT, session TEXT, payload TEXT)")
            con.execute(CATALOG_DDL)

    @property
    def kind(self) -> str:
        return "postgres" if self.pg else "sqlite"

    def _conn(self):
        # prepare_threshold=None: works with Supabase's transaction pooler (port 6543)
        return self._psycopg.connect(self.url, autocommit=True, prepare_threshold=None) if self.pg else sqlite3.connect(DB_PATH)

    def log(self, kind: str, session: str, payload: dict):
        ph = "%s" if self.pg else "?"
        with self._conn() as con:
            con.execute(f"INSERT INTO log(ts, kind, session, payload) VALUES ({ph},{ph},{ph},{ph})",
                        (time.time(), kind, session, json.dumps(payload, ensure_ascii=False)))

    def catalog_put(self, kind: str, item_id: str, payload: dict | None):
        ph = "%s" if self.pg else "?"
        with self._conn() as con:
            con.execute(f"INSERT INTO catalog(kind, item_id, payload, ts) VALUES ({ph},{ph},{ph},{ph}) "
                        "ON CONFLICT (kind, item_id) DO UPDATE SET payload = EXCLUDED.payload, ts = EXCLUDED.ts",
                        (kind, item_id, None if payload is None else json.dumps(payload, ensure_ascii=False), time.time()))

    def catalog_reset(self, kind: str, item_id: str):
        ph = "%s" if self.pg else "?"
        with self._conn() as con:
            con.execute(f"DELETE FROM catalog WHERE kind = {ph} AND item_id = {ph}", (kind, item_id))

    def catalog_rows(self) -> list[tuple[str, str, dict | None, float]]:
        with self._conn() as con:
            rows = con.execute("SELECT kind, item_id, payload, ts FROM catalog ORDER BY ts").fetchall()
        return [(k, i, None if p is None else json.loads(p), t) for k, i, p, t in rows]

    def export(self) -> list[dict]:
        with self._conn() as con:
            rows = con.execute("SELECT ts, kind, session, payload FROM log ORDER BY id").fetchall()
        return [{"ts": t, "kind": k, "session": s, **json.loads(p)} for t, k, s, p in rows]
