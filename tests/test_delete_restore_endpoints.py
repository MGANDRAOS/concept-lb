import json
from datetime import datetime, timezone

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
        plan = {
            "plan_meta": {"concept_name": "Test"},
            "sections": [
                {"id": "mission", "title": "Mission",
                 "blocks": [{"type": "paragraph", "text": "mission content"},
                            {"type": "bullets", "items": ["a"]}]},
                {"id": "vision", "title": "Vision",
                 "blocks": [{"type": "paragraph", "text": "v"}]},
            ],
        }
        conn.execute(
            "INSERT INTO plans (id, created_at, updated_at, status, intake_json, plan_json, plan_html) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("p-d", now, now, "complete", "{}", json.dumps(plan), "<html/>"),
        )
        conn.commit()
    finally:
        conn.close()
    return "p-d"


def test_delete_section_removes_from_plan_and_records_snapshot(client, tmp_path, monkeypatch):
    pid = _seed(tmp_path)
    monkeypatch.setattr(app_module, "render_template", lambda *a, **k: "<html>new</html>")
    resp = client.delete(f"/api/plans/{pid}/sections/mission")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["deleted_section_ids"] == ["mission"]
    assert body["plan_html"] == "<html>new</html>"

    # Plan JSON no longer contains mission
    from orchestration.db import connect
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    row = conn.execute(
        "SELECT plan_json, deleted_section_ids_json FROM plans WHERE id=?",
        (pid,),
    ).fetchone()
    pj = json.loads(row["plan_json"])
    assert [s["id"] for s in pj["sections"]] == ["vision"]
    assert json.loads(row["deleted_section_ids_json"]) == ["mission"]

    # A revision snapshot was recorded
    rev = conn.execute(
        "SELECT user_comment FROM section_revisions WHERE plan_id=? AND section_id=?",
        (pid, "mission"),
    ).fetchone()
    assert rev is not None
    assert "(deleted" in rev["user_comment"]
    conn.close()


def test_delete_section_404_for_unknown_plan(client):
    resp = client.delete("/api/plans/missing/sections/mission")
    assert resp.status_code == 404


def test_delete_section_404_for_unknown_section(client, tmp_path):
    pid = _seed(tmp_path)
    resp = client.delete(f"/api/plans/{pid}/sections/does_not_exist")
    assert resp.status_code == 404


def test_restore_deleted_section_reinserts_at_spec_order(client, tmp_path, monkeypatch):
    pid = _seed(tmp_path)
    monkeypatch.setattr(app_module, "render_template", lambda *a, **k: "<html>r</html>")
    client.delete(f"/api/plans/{pid}/sections/mission")
    resp = client.post(f"/api/plans/{pid}/sections/mission/restore")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert "mission" not in body["deleted_section_ids"]

    # mission should be back in plan_json
    from orchestration.db import connect
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    row = conn.execute("SELECT plan_json, deleted_section_ids_json FROM plans WHERE id=?", (pid,)).fetchone()
    pj = json.loads(row["plan_json"])
    section_ids = [s["id"] for s in pj["sections"]]
    assert "mission" in section_ids
    # mission has order=2, vision order=3 in SECTION_SPECS, so mission first
    assert section_ids.index("mission") < section_ids.index("vision")
    assert row["deleted_section_ids_json"] in (None, "", "[]")
    conn.close()


def test_restore_400_when_not_deleted(client, tmp_path):
    pid = _seed(tmp_path)
    resp = client.post(f"/api/plans/{pid}/sections/mission/restore")
    assert resp.status_code == 400


def test_single_regenerate_refuses_deleted_section(client, tmp_path, monkeypatch):
    pid = _seed(tmp_path)
    monkeypatch.setattr(app_module, "render_template", lambda *a, **k: "<html/>")
    client.delete(f"/api/plans/{pid}/sections/mission")
    resp = client.post(
        f"/api/plans/{pid}/sections/mission/regenerate",
        json={"user_comment": "x", "regenerate_image": False},
    )
    assert resp.status_code == 400
    assert "deleted" in resp.get_json()["error"].lower()
