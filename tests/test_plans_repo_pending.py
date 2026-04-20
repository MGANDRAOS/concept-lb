import json
from datetime import datetime, timezone

import pytest

from orchestration.db import connect, init_db
from orchestration.plans_repo import get_plan
from orchestration.pending_edits_repo import set_pending_edit


@pytest.fixture
def db(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO plans (id, created_at, updated_at, status, intake_json, plan_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("p1", now, now, "complete", "{}", json.dumps({"sections": []})),
    )
    conn.commit()
    yield conn
    conn.close()


def test_plan_view_pending_edits_empty_by_default(db):
    view = get_plan(db, "p1")
    assert view is not None
    assert view.pending_edits == {}


def test_plan_view_reads_pending_edits(db):
    set_pending_edit(db, plan_id="p1", section_id="mission",
                     blocks=[{"type": "paragraph", "text": "x"}],
                     user_comment="short")
    view = get_plan(db, "p1")
    assert "mission" in view.pending_edits
    assert view.pending_edits["mission"]["user_comment"] == "short"
