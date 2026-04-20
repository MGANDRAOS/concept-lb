from orchestration.db import connect, init_db


def test_plans_has_pending_edits_json_column(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(plans)").fetchall()]
        assert "pending_edits_json" in cols
    finally:
        conn.close()
