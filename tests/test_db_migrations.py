import os

from orchestration.db import init_db, connect


def test_section_revisions_table_exists(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='section_revisions'"
        ).fetchall()
        assert len(rows) == 1, "section_revisions table should exist after init_db"
    finally:
        conn.close()


def test_plans_has_stale_section_ids_column(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(plans)").fetchall()]
        assert "stale_section_ids" in cols
    finally:
        conn.close()
