# orchestration/db.py
import os
import sqlite3
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT,
  mode TEXT,
  locale TEXT,
  model TEXT,
  job_id TEXT,

  intake_json TEXT NOT NULL,
  normalized_intake_json TEXT,
  plan_json TEXT,
  plan_html TEXT,

  tokens_in INTEGER,
  tokens_out INTEGER,
  latency_ms INTEGER,
  error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans(created_at);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_job_id ON plans(job_id);

CREATE TABLE IF NOT EXISTS section_revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL,
  section_id TEXT NOT NULL,
  section_title TEXT NOT NULL,
  user_comment TEXT,
  blocks_json TEXT NOT NULL,
  image_url TEXT,
  image_alt TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sec_rev_plan ON section_revisions(plan_id);
CREATE INDEX IF NOT EXISTS idx_sec_rev_plan_section ON section_revisions(plan_id, section_id);
CREATE INDEX IF NOT EXISTS idx_sec_rev_created ON section_revisions(created_at);
"""


def ensure_instance_folder(instance_path: str) -> None:
    os.makedirs(instance_path, exist_ok=True)


def get_db_path(instance_path: str) -> str:
    return os.path.join(instance_path, "concept_lb.sqlite")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(instance_path: str) -> str:
    """Ensure folder + schema; applies idempotent column additions for legacy DBs."""
    ensure_instance_folder(instance_path)
    db_path = get_db_path(instance_path)

    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _add_column_if_missing(conn, "plans", "stale_section_ids", "TEXT")
        _add_column_if_missing(conn, "plans", "pending_edits_json", "TEXT")
        conn.commit()
    finally:
        conn.close()

    return db_path
