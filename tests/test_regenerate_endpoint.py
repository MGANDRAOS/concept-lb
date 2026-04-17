import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Redirect Flask instance path to a tmp dir so tests don't touch real DB
    monkeypatch.setattr(app_module.app, "instance_path", str(tmp_path))
    from orchestration.db import init_db
    db_path = init_db(str(tmp_path))
    monkeypatch.setattr(app_module, "DB_PATH", db_path)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _seed_plan(db_path: str) -> str:
    from orchestration.db import connect
    conn = connect(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        plan = {
            "plan_meta": {"concept_name": "Test"},
            "sections": [
                {"id": "mission", "title": "Mission",
                 "blocks": [{"type": "paragraph", "text": "old"}, {"type": "bullets", "items": ["a"]}]},
                {"id": "vision", "title": "Vision",
                 "blocks": [{"type": "paragraph", "text": "v"}, {"type": "bullets", "items": ["b"]}]},
            ],
        }
        conn.execute(
            "INSERT INTO plans (id, created_at, updated_at, status, intake_json, normalized_intake_json, plan_json, plan_html) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("p-test", now, now, "complete", "{}",
             json.dumps({"concept_name": "Test", "cuisine_type": "pizza", "city": "Beirut"}),
             json.dumps(plan), "<html>old</html>"),
        )
        conn.commit()
    finally:
        conn.close()
    return "p-test"


def test_regenerate_happy_path(client, tmp_path, monkeypatch):
    from orchestration.db import connect
    plan_id = _seed_plan(str(tmp_path) + "/concept_lb.sqlite")

    new_section = {
        "id": "mission",
        "title": "Mission",
        "blocks": [
            {"type": "paragraph", "text": "NEW mission"},
            {"type": "bullets", "items": ["x", "y"]},
        ],
    }

    with patch("app.regenerate_section", return_value=new_section), \
         patch("app.render_template", return_value="<html>rerendered</html>"):
        resp = client.post(
            f"/api/plans/{plan_id}/sections/mission/regenerate",
            json={"user_comment": "Make it punchier.", "regenerate_image": False},
        )

    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["section"]["id"] == "mission"
    assert body["plan_html"] == "<html>rerendered</html>"
    assert "vision" not in body["stale_section_ids"]  # mission doesn't invalidate vision


def test_regenerate_unknown_plan_returns_404(client):
    resp = client.post(
        "/api/plans/does-not-exist/sections/mission/regenerate",
        json={"user_comment": "x", "regenerate_image": False},
    )
    assert resp.status_code == 404


def test_regenerate_unknown_section_returns_400(client, tmp_path):
    plan_id = _seed_plan(str(tmp_path) + "/concept_lb.sqlite")
    resp = client.post(
        f"/api/plans/{plan_id}/sections/not_a_section/regenerate",
        json={"user_comment": "x", "regenerate_image": False},
    )
    assert resp.status_code == 400


def test_regenerate_concept_overview_marks_many_stale(client, tmp_path):
    from orchestration.db import connect
    plan_id = _seed_plan(str(tmp_path) + "/concept_lb.sqlite")
    # Add a concept_overview section to the seeded plan so we can edit it
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    row = conn.execute("SELECT plan_json FROM plans WHERE id = ?", (plan_id,)).fetchone()
    plan = json.loads(row["plan_json"])
    plan["sections"].insert(
        0,
        {"id": "concept_overview", "title": "Concept Overview",
         "blocks": [{"type": "paragraph", "text": "old"}, {"type": "bullets", "items": ["a"]}]},
    )
    conn.execute("UPDATE plans SET plan_json = ? WHERE id = ?",
                 (json.dumps(plan), plan_id))
    conn.commit()
    conn.close()

    new_section = {
        "id": "concept_overview", "title": "Concept Overview",
        "blocks": [{"type": "paragraph", "text": "NEW"}, {"type": "bullets", "items": ["x"]}],
    }
    with patch("app.regenerate_section", return_value=new_section), \
         patch("app.render_template", return_value="<html>r</html>"):
        resp = client.post(
            f"/api/plans/{plan_id}/sections/concept_overview/regenerate",
            json={"user_comment": "x", "regenerate_image": False},
        )

    assert resp.status_code == 200
    stale = set(resp.get_json()["stale_section_ids"])
    assert "brand_positioning" in stale
    assert "menu_structure" in stale
    assert "concept_overview" not in stale  # the edited section is NOT stale
