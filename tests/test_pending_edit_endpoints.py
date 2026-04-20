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


def _seed_plan(tmp_path) -> str:
    from orchestration.db import connect
    conn = connect(str(tmp_path) + "/concept_lb.sqlite")
    try:
        now = datetime.now(timezone.utc).isoformat()
        plan = {"plan_meta": {"concept_name": "Test"},
                "sections": [{"id": "mission", "title": "Mission",
                              "blocks": [{"type": "paragraph", "text": "old"}]}]}
        conn.execute(
            "INSERT INTO plans (id, created_at, updated_at, status, intake_json, plan_json, plan_html) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("p-t", now, now, "complete", "{}", json.dumps(plan), "<html/>"),
        )
        conn.commit()
    finally:
        conn.close()
    return "p-t"


def test_put_pending_creates_entry(client, tmp_path):
    pid = _seed_plan(tmp_path)
    resp = client.put(
        f"/api/plans/{pid}/sections/mission/pending",
        json={"blocks": [{"type": "paragraph", "text": "NEW"}],
              "user_comment": "shorter"},
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["pending"]["blocks"][0]["text"] == "NEW"


def test_get_pending_lists_all(client, tmp_path):
    pid = _seed_plan(tmp_path)
    client.put(f"/api/plans/{pid}/sections/mission/pending",
               json={"blocks": [], "user_comment": "x"})
    resp = client.get(f"/api/plans/{pid}/pending")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "mission" in body["edits"]


def test_delete_pending_removes(client, tmp_path):
    pid = _seed_plan(tmp_path)
    client.put(f"/api/plans/{pid}/sections/mission/pending",
               json={"blocks": [], "user_comment": "x"})
    resp = client.delete(f"/api/plans/{pid}/sections/mission/pending")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    resp2 = client.get(f"/api/plans/{pid}/pending")
    assert resp2.get_json()["edits"] == {}


def test_put_pending_rejects_unknown_plan(client):
    resp = client.put(
        "/api/plans/missing/sections/mission/pending",
        json={"blocks": [], "user_comment": ""},
    )
    assert resp.status_code == 404


def test_put_pending_rejects_invalid_blocks(client, tmp_path):
    pid = _seed_plan(tmp_path)
    resp = client.put(
        f"/api/plans/{pid}/sections/mission/pending",
        json={"blocks": "not-a-list", "user_comment": ""},
    )
    assert resp.status_code == 400
