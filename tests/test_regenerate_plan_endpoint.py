import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.app, "instance_path", str(tmp_path))
    from orchestration.db import init_db
    db_path = init_db(str(tmp_path))
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _seed(tmp_path) -> str:
    from orchestration.db import connect
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    try:
        now = datetime.now(timezone.utc).isoformat()
        plan = {"plan_meta": {"concept_name": "Test"},
                "sections": [
                    {"id": "mission", "title": "Mission",
                     "blocks": [{"type": "paragraph", "text": "old"},
                                {"type": "bullets", "items": ["a"]}]},
                    {"id": "vision", "title": "Vision",
                     "blocks": [{"type": "paragraph", "text": "v"},
                                {"type": "bullets", "items": ["b"]}]},
                ]}
        conn.execute(
            "INSERT INTO plans (id, created_at, updated_at, status, intake_json, "
            "normalized_intake_json, plan_json, plan_html, model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p-t", now, now, "complete", "{}",
             json.dumps({"concept_name": "T", "cuisine_type": "Cafe"}),
             json.dumps(plan), "<html/>", "gpt-5.4-nano-2026-03-17"),
        )
        conn.execute(
            "UPDATE plans SET pending_edits_json = ? WHERE id = ?",
            (json.dumps({
                "mission": {
                    "blocks": [{"type": "paragraph", "text": "user wrote this"}],
                    "user_comment": "shorter",
                    "updated_at": now,
                }
            }), "p-t"),
        )
        conn.commit()
    finally:
        conn.close()
    return "p-t"


def _fake_full_regen():
    return (
        [
            {"id": "mission", "title": "Mission",
             "blocks": [{"type": "paragraph", "text": "mission NEW"},
                        {"type": "bullets", "items": ["x"]}]},
            {"id": "vision", "title": "Vision",
             "blocks": [{"type": "paragraph", "text": "vision NEW"},
                        {"type": "bullets", "items": ["y"]}]},
        ],
        ["mission"],
    )


def test_regenerate_plan_applies_sections_and_clears_pending(client, tmp_path):
    pid = _seed(tmp_path)
    with patch("app.regenerate_full_plan", return_value=_fake_full_regen()), \
         patch("app.render_template", return_value="<html>NEW</html>"):
        resp = client.post(f"/api/plans/{pid}/regenerate-plan", json={})
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["plan_html"] == "<html>NEW</html>"
    assert body["applied_edit_section_ids"] == ["mission"]
    assert body["stale_section_ids"] == []

    from orchestration.db import connect
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    row = conn.execute("SELECT pending_edits_json, plan_json FROM plans WHERE id=?",
                       (pid,)).fetchone()
    assert row["pending_edits_json"] in (None, "", "{}")
    pj = json.loads(row["plan_json"])
    assert pj["sections"][0]["blocks"][0]["text"] == "mission NEW"
    conn.close()


def test_regenerate_plan_404_when_plan_missing(client):
    resp = client.post("/api/plans/missing/regenerate-plan", json={})
    assert resp.status_code == 404


def test_regenerate_plan_400_when_no_pending_and_not_forced(client, tmp_path):
    from orchestration.db import connect
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    now = datetime.now(timezone.utc).isoformat()
    plan = {"sections": []}
    conn.execute(
        "INSERT INTO plans (id, created_at, updated_at, status, intake_json, plan_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("p-empty", now, now, "complete", "{}", json.dumps(plan)),
    )
    conn.commit()
    conn.close()
    resp = client.post("/api/plans/p-empty/regenerate-plan", json={})
    assert resp.status_code == 400
