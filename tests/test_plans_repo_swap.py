import json
from datetime import datetime, timezone

import pytest

from orchestration.db import connect, init_db
from orchestration.plans_repo import (
    apply_section_update,
    get_plan,
)


@pytest.fixture
def db(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    plan_json = {
        "plan_meta": {"concept_name": "Test"},
        "sections": [
            {"id": "mission", "title": "Mission",
             "blocks": [{"type": "paragraph", "text": "old"}]},
            {"id": "vision", "title": "Vision",
             "blocks": [{"type": "paragraph", "text": "v"}]},
        ],
    }
    conn.execute(
        "INSERT INTO plans (id, created_at, updated_at, status, intake_json, plan_json, plan_html) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("p1", now, now, "complete", "{}", json.dumps(plan_json), "<html>old</html>"),
    )
    conn.commit()
    yield conn
    conn.close()


def test_apply_section_update_replaces_section_and_persists_html_and_stale(db):
    new_section = {
        "id": "mission",
        "title": "Mission",
        "blocks": [{"type": "paragraph", "text": "NEW"}],
    }
    apply_section_update(
        db,
        plan_id="p1",
        new_section=new_section,
        new_plan_html="<html>NEW</html>",
        stale_section_ids={"vision"},
    )

    view = get_plan(db, "p1")
    assert view is not None
    assert view.plan_html == "<html>NEW</html>"
    mission = [s for s in view.plan["sections"] if s["id"] == "mission"][0]
    assert mission["blocks"][0]["text"] == "NEW"
    assert view.stale_section_ids == ["vision"]


def test_apply_section_update_preserves_other_sections(db):
    new_section = {
        "id": "mission",
        "title": "Mission",
        "blocks": [{"type": "paragraph", "text": "NEW"}],
    }
    apply_section_update(
        db,
        plan_id="p1",
        new_section=new_section,
        new_plan_html="<html>NEW</html>",
        stale_section_ids=set(),
    )
    view = get_plan(db, "p1")
    vision = [s for s in view.plan["sections"] if s["id"] == "vision"][0]
    assert vision["blocks"][0]["text"] == "v"


def test_apply_section_update_raises_for_unknown_plan(db):
    with pytest.raises(ValueError, match="plan not found"):
        apply_section_update(
            db,
            plan_id="not-real",
            new_section={"id": "mission", "title": "Mission", "blocks": []},
            new_plan_html="x",
            stale_section_ids=set(),
        )
