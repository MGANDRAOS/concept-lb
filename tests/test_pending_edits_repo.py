import json
from datetime import datetime, timezone

import pytest

from orchestration.db import connect, init_db
from orchestration.pending_edits_repo import (
    get_pending_edits,
    set_pending_edit,
    clear_pending_edit,
    clear_all_pending,
)


@pytest.fixture
def db(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO plans (id, created_at, updated_at, status, intake_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p1", now, now, "complete", "{}"),
    )
    conn.commit()
    yield conn
    conn.close()


def test_empty_by_default(db):
    assert get_pending_edits(db, "p1") == {}


def test_set_and_get(db):
    set_pending_edit(
        db,
        plan_id="p1",
        section_id="mission",
        blocks=[{"type": "paragraph", "text": "new"}],
        user_comment="shorter",
    )
    edits = get_pending_edits(db, "p1")
    assert "mission" in edits
    assert edits["mission"]["blocks"][0]["text"] == "new"
    assert edits["mission"]["user_comment"] == "shorter"
    assert "updated_at" in edits["mission"]


def test_update_overwrites(db):
    set_pending_edit(db, plan_id="p1", section_id="mission",
                     blocks=[{"type": "paragraph", "text": "v1"}], user_comment="a")
    set_pending_edit(db, plan_id="p1", section_id="mission",
                     blocks=[{"type": "paragraph", "text": "v2"}], user_comment="b")
    edits = get_pending_edits(db, "p1")
    assert edits["mission"]["blocks"][0]["text"] == "v2"
    assert edits["mission"]["user_comment"] == "b"


def test_multiple_sections_and_clear_one(db):
    set_pending_edit(db, plan_id="p1", section_id="mission", blocks=[], user_comment="x")
    set_pending_edit(db, plan_id="p1", section_id="vision", blocks=[], user_comment="y")
    assert set(get_pending_edits(db, "p1").keys()) == {"mission", "vision"}
    clear_pending_edit(db, plan_id="p1", section_id="mission")
    assert list(get_pending_edits(db, "p1").keys()) == ["vision"]


def test_clear_all(db):
    set_pending_edit(db, plan_id="p1", section_id="mission", blocks=[], user_comment="x")
    set_pending_edit(db, plan_id="p1", section_id="vision", blocks=[], user_comment="y")
    clear_all_pending(db, plan_id="p1")
    assert get_pending_edits(db, "p1") == {}


def test_unknown_plan_raises(db):
    with pytest.raises(ValueError, match="plan not found"):
        set_pending_edit(db, plan_id="nope", section_id="mission",
                         blocks=[], user_comment="x")
