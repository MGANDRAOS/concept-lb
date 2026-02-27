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
"""

def ensure_instance_folder(instance_path: str) -> None:
    os.makedirs(instance_path, exist_ok=True)

def get_db_path(instance_path: str) -> str:
    return os.path.join(instance_path, "concept_lb.sqlite")

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(instance_path: str) -> str:
    """
    Ensures instance folder exists, creates DB file if missing, and applies schema.
    Returns absolute db_path.
    """
    ensure_instance_folder(instance_path)
    db_path = get_db_path(instance_path)

    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()

    return db_path