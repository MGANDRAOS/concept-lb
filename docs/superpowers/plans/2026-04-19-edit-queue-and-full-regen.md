# Edit Queue + Full Plan Regen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Let users directly edit the content of any section in a rich form, queue multiple edits, then run a single "Regenerate Plan" pass that regenerates every section with those edits as context so the whole plan stays coherent.

**Architecture:** A new `pending_edits_json` column on `plans` stores a dict `{section_id: {blocks, user_comment, updated_at}}`. The existing per-section regenerate endpoint stays for quick one-offs; new endpoints add/update/delete pending edits and a new full-plan regenerate endpoint runs `generate_sections_bundle` with a "user feedback" preamble injecting the queued edits. The edit modal is rewritten from a single comment textarea into a rich per-block editor (paragraphs, bullets, menu items, callouts) so users replace actual copy. Sidebar gets a global "Regenerate Plan (N edits)" button + per-section pending badges.

**Tech Stack:** Flask, SQLite, Pydantic, OpenAI Responses API, vanilla JS (no framework), pytest.

---

## File Structure

**Create:**
- `orchestration/pending_edits_repo.py` — CRUD on `plans.pending_edits_json`
- `orchestration/full_plan_regenerator.py` — full-plan regen that reuses `generate_sections_bundle` with edits as context
- `tests/test_pending_edits_repo.py`
- `tests/test_full_plan_regenerator.py`
- `tests/test_pending_edit_endpoints.py`
- `tests/test_regenerate_plan_endpoint.py`

**Modify:**
- `orchestration/db.py` — add `pending_edits_json TEXT` via `_add_column_if_missing`
- `orchestration/plans_repo.py` — read/write `pending_edits_json` in `get_plan` + a helper `clear_pending_edits`
- `schemas/plan_store_schema.py` — add `pending_edits: Dict[str, Any]` to `PlanView`
- `app.py` — 4 new routes + pass pending state to `plan_detail.html`
- `templates/plan_detail.html` — rich modal + global Regenerate Plan button + Pending badges
- `static/css/section_edit.css` — styles for rich block editors + pending badge + global button
- `static/js/section_edit.js` — fetch current section, render editors, save-to-queue vs regenerate-now, global regen click, pending state sync

---

## Task 1: Schema — add `pending_edits_json` column

**Files:**
- Modify: `orchestration/db.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_db_pending_edits_column.py`:

```python
from orchestration.db import connect, init_db


def test_plans_has_pending_edits_json_column(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(plans)").fetchall()]
        assert "pending_edits_json" in cols
    finally:
        conn.close()
```

- [ ] **Step 2: Run, confirm FAIL**

`pytest tests/test_db_pending_edits_column.py -v`

- [ ] **Step 3: Add column**

In `orchestration/db.py`, inside `init_db`, add another `_add_column_if_missing` call alongside the existing `stale_section_ids` one:

```python
    _add_column_if_missing(conn, "plans", "stale_section_ids", "TEXT")
    _add_column_if_missing(conn, "plans", "pending_edits_json", "TEXT")
```

- [ ] **Step 4: Verify PASS**

`pytest tests/test_db_pending_edits_column.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestration/db.py tests/test_db_pending_edits_column.py
git commit -m "feat(db): add pending_edits_json column to plans"
```

---

## Task 2: Pending edits repo

**Files:**
- Create: `orchestration/pending_edits_repo.py`
- Create: `tests/test_pending_edits_repo.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Implement**

Create `orchestration/pending_edits_repo.py`:

```python
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _load(conn: sqlite3.Connection, plan_id: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT pending_edits_json FROM plans WHERE id = ?",
        (plan_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"plan not found: {plan_id!r}")
    raw = row["pending_edits_json"]
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _save(conn: sqlite3.Connection, plan_id: str, edits: Dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE plans SET pending_edits_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(edits, ensure_ascii=False), now, plan_id),
    )
    conn.commit()


def get_pending_edits(conn: sqlite3.Connection, plan_id: str) -> Dict[str, Any]:
    try:
        return _load(conn, plan_id)
    except ValueError:
        return {}


def set_pending_edit(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    section_id: str,
    blocks: List[Dict[str, Any]],
    user_comment: Optional[str],
) -> None:
    edits = _load(conn, plan_id)
    edits[section_id] = {
        "blocks": blocks,
        "user_comment": user_comment or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(conn, plan_id, edits)


def clear_pending_edit(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    section_id: str,
) -> None:
    edits = _load(conn, plan_id)
    edits.pop(section_id, None)
    _save(conn, plan_id, edits)


def clear_all_pending(conn: sqlite3.Connection, plan_id: str) -> None:
    _load(conn, plan_id)  # raise if missing
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE plans SET pending_edits_json = NULL, updated_at = ? WHERE id = ?",
        (now, plan_id),
    )
    conn.commit()
```

- [ ] **Step 4: Verify 6 PASS**

- [ ] **Step 5: Commit**

```bash
git add orchestration/pending_edits_repo.py tests/test_pending_edits_repo.py
git commit -m "feat: pending_edits_repo (CRUD for queued section edits)"
```

---

## Task 3: Plans_repo + PlanView exposes pending_edits

**Files:**
- Modify: `orchestration/plans_repo.py`
- Modify: `schemas/plan_store_schema.py`
- Create: `tests/test_plans_repo_pending.py`

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run FAIL**

- [ ] **Step 3: Update `PlanView` schema**

In `schemas/plan_store_schema.py`, add a new field:

```python
pending_edits: Dict[str, Any] = Field(default_factory=dict)
```

Ensure `Dict`, `Any`, `Field` imports exist.

- [ ] **Step 4: Update `get_plan` in `plans_repo.py`**

Inside `get_plan`, parse the column similar to how `stale_ids_raw` is parsed. Near the existing `stale_ids_raw` block, add:

```python
    pending_raw = r["pending_edits_json"] if "pending_edits_json" in r.keys() else None
    pending_edits: dict = {}
    if pending_raw:
        try:
            p = json.loads(pending_raw)
            if isinstance(p, dict):
                pending_edits = p
        except Exception:
            pending_edits = {}
```

Then pass `pending_edits=pending_edits` into `PlanView(...)`.

- [ ] **Step 5: Verify 2 PASS**

- [ ] **Step 6: Commit**

```bash
git add orchestration/plans_repo.py schemas/plan_store_schema.py tests/test_plans_repo_pending.py
git commit -m "feat: PlanView.pending_edits readback from plans_repo"
```

---

## Task 4: API — pending edit CRUD endpoints

**Files:**
- Modify: `app.py`
- Create: `tests/test_pending_edit_endpoints.py`

- [ ] **Step 1: Write failing test**

```python
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
    # verify cleared
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
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement endpoints in `app.py`**

Import at top (alongside existing orchestration imports):

```python
from orchestration.pending_edits_repo import (
    get_pending_edits,
    set_pending_edit,
    clear_pending_edit,
)
```

Add routes (place near the existing `api_regenerate_section` and `api_revert_section` block):

```python
@app.route("/api/plans/<plan_id>/sections/<section_id>/pending", methods=["PUT"])
def api_set_pending_edit(plan_id: str, section_id: str):
    payload = request.get_json(silent=True) or {}
    blocks = payload.get("blocks")
    user_comment = (payload.get("user_comment") or "").strip()
    if not isinstance(blocks, list):
        return jsonify({"ok": False, "error": "blocks must be a list"}), 400

    conn = db_conn()
    try:
        pv = get_plan(conn, plan_id)
        if pv is None:
            return jsonify({"ok": False, "error": "plan not found"}), 404
        try:
            set_pending_edit(conn, plan_id=plan_id, section_id=section_id,
                             blocks=blocks, user_comment=user_comment)
        except ValueError as ve:
            return jsonify({"ok": False, "error": str(ve)}), 404
        edits = get_pending_edits(conn, plan_id)
        return jsonify({"ok": True, "pending": edits.get(section_id, {}),
                        "pending_section_ids": sorted(edits.keys())})
    finally:
        conn.close()


@app.route("/api/plans/<plan_id>/sections/<section_id>/pending", methods=["DELETE"])
def api_clear_pending_edit(plan_id: str, section_id: str):
    conn = db_conn()
    try:
        pv = get_plan(conn, plan_id)
        if pv is None:
            return jsonify({"ok": False, "error": "plan not found"}), 404
        clear_pending_edit(conn, plan_id=plan_id, section_id=section_id)
        edits = get_pending_edits(conn, plan_id)
        return jsonify({"ok": True, "pending_section_ids": sorted(edits.keys())})
    finally:
        conn.close()


@app.route("/api/plans/<plan_id>/pending", methods=["GET"])
def api_list_pending_edits(plan_id: str):
    conn = db_conn()
    try:
        pv = get_plan(conn, plan_id)
        if pv is None:
            return jsonify({"ok": False, "error": "plan not found"}), 404
        edits = get_pending_edits(conn, plan_id)
        return jsonify({"ok": True, "edits": edits})
    finally:
        conn.close()
```

- [ ] **Step 4: Run 5 PASS**

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_pending_edit_endpoints.py
git commit -m "feat: pending-edit CRUD endpoints (PUT/DELETE/GET)"
```

---

## Task 5: Full-plan regenerator (reuses section_bundle_generator)

**Files:**
- Create: `orchestration/full_plan_regenerator.py`
- Create: `tests/test_full_plan_regenerator.py`

The module: given a concept, the current plan sections, and a dict of pending edits, it builds a "user feedback" prelude and calls `generate_sections_bundle` across all included specs — with the pending edits forced as anchors the model must respect.

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch

import pytest

from orchestration.full_plan_regenerator import regenerate_full_plan


def _fake_bundle_response():
    # One section returned by the bundle generator
    return {
        "sections": [
            {"id": "mission", "title": "Mission",
             "blocks": [{"type": "paragraph", "text": "regenerated mission respecting user edit"},
                        {"type": "bullets", "items": ["a", "b"]}]},
        ]
    }


def test_regenerate_full_plan_passes_pending_edits_to_bundle_generator(fake_concept):
    pending = {
        "mission": {
            "blocks": [{"type": "paragraph", "text": "USER-TYPED REPLACEMENT"}],
            "user_comment": "tone should be conservative",
            "updated_at": "2026-04-19T00:00:00Z",
        },
    }
    existing_sections = [
        {"id": "mission", "title": "Mission",
         "blocks": [{"type": "paragraph", "text": "old"},
                    {"type": "bullets", "items": ["old-a", "old-b"]}]},
    ]

    with patch("orchestration.full_plan_regenerator.generate_sections_bundle",
               return_value=_fake_bundle_response()) as mocked:
        new_sections, used_edits = regenerate_full_plan(
            concept=fake_concept,
            existing_sections=existing_sections,
            pending_edits=pending,
            model_name="gpt-5.4-nano-2026-03-17",
        )

    assert len(new_sections) == 1
    assert new_sections[0]["id"] == "mission"
    assert used_edits == ["mission"]

    _, kwargs = mocked.call_args
    # The concept passed in must include the feedback block that the user typed
    concept_arg = kwargs["concept"]
    assert "USER-TYPED REPLACEMENT" in str(concept_arg)
    assert "tone should be conservative" in str(concept_arg)


def test_regenerate_full_plan_with_no_pending_still_runs(fake_concept):
    existing_sections = [
        {"id": "mission", "title": "Mission",
         "blocks": [{"type": "paragraph", "text": "old"},
                    {"type": "bullets", "items": ["a"]}]},
    ]
    with patch("orchestration.full_plan_regenerator.generate_sections_bundle",
               return_value=_fake_bundle_response()):
        new_sections, used_edits = regenerate_full_plan(
            concept=fake_concept,
            existing_sections=existing_sections,
            pending_edits={},
            model_name="gpt-5.4-nano-2026-03-17",
        )
    assert used_edits == []
    assert len(new_sections) == 1
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Create `orchestration/full_plan_regenerator.py`:

```python
from typing import Any, Dict, List, Optional, Tuple

from orchestration.section_bundle_generator import generate_sections_bundle
from orchestration.section_specs import SECTION_SPECS, should_include_section


_FEEDBACK_TEMPLATE = """
USER FEEDBACK (user-authored edits to specific sections — TREAT AS HARD ANCHORS):
{edits_text}

Instructions for this full-plan regeneration:
- Where the user has provided replacement blocks for a section, incorporate their
  exact wording and structural intent into that section's output.
- Where the user left a steering comment, apply it to the relevant section's tone,
  emphasis, or content.
- When other sections reference topics the user just changed, update those
  references to stay coherent with the new wording / direction.
- Do NOT undo the user's changes or paraphrase them away.
""".strip()


def _format_edit(section_id: str, edit: Dict[str, Any]) -> str:
    blocks_json = str(edit.get("blocks") or [])
    comment = (edit.get("user_comment") or "").strip()
    parts = [f'- Section "{section_id}":']
    if blocks_json and blocks_json != "[]":
        parts.append(f"  User-typed blocks (authoritative): {blocks_json}")
    if comment:
        parts.append(f"  User comment: {comment}")
    return "\n".join(parts)


def regenerate_full_plan(
    *,
    concept: Dict[str, Any],
    existing_sections: List[Dict[str, Any]],
    pending_edits: Dict[str, Any],
    model_name: Optional[str] = None,
    chunk_size: int = 4,
    max_output_tokens: int = 8000,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Regenerate all applicable sections using pending_edits as strong context.

    Returns (new_sections, used_edit_section_ids).
    """
    # Build the feedback concept: shallow-copy concept and inject a feedback block.
    concept_with_feedback = dict(concept or {})
    used_edit_ids: List[str] = sorted(pending_edits.keys()) if pending_edits else []

    if pending_edits:
        edits_text = "\n".join(
            _format_edit(sid, pending_edits[sid]) for sid in used_edit_ids
        )
        concept_with_feedback["__user_feedback__"] = _FEEDBACK_TEMPLATE.format(
            edits_text=edits_text
        )

    # Resolve which section specs apply to this concept.
    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))

    # Regenerate in chunks.
    new_sections: List[Dict[str, Any]] = []
    chunks = [
        included_specs[i : i + chunk_size]
        for i in range(0, len(included_specs), chunk_size)
    ]
    for idx, specs_chunk in enumerate(chunks):
        include_assumptions = (idx == len(chunks) - 1)
        bundle = generate_sections_bundle(
            concept=concept_with_feedback,
            section_specs=specs_chunk,
            include_assumptions=include_assumptions,
            model_name=model_name or "gpt-5.4-nano-2026-03-17",
            max_output_tokens=max_output_tokens,
            generate_images=False,
        )
        new_sections.extend(bundle.get("sections") or [])

    return new_sections, used_edit_ids
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add orchestration/full_plan_regenerator.py tests/test_full_plan_regenerator.py
git commit -m "feat: full-plan regenerator driven by queued user edits"
```

---

## Task 6: Full-plan regenerate endpoint

**Files:**
- Modify: `app.py`
- Create: `tests/test_regenerate_plan_endpoint.py`

The endpoint:
- 404 if plan missing
- 400 if there are no queued pending edits AND user didn't pass `force=true`
- Calls `regenerate_full_plan`, swaps every section in `plan_json`, preserves existing image blocks on unedited sections (so we don't need to regenerate images)
- Clears `pending_edits_json` and `stale_section_ids`
- Inserts one revision row per section (user_comment = `"(full plan regen — edited: sid1, sid2)"` for edited sections; `"(full plan regen)"` for unedited)
- Re-renders `plan_html`, persists via the existing update path (but we can't use `apply_section_update` since it's single-section — use direct SQL similar to how the job generator persists the plan)

- [ ] **Step 1: Write failing test**

```python
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
        # Queue one edit
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
    # Seed a plan without any pending edits
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Imports in `app.py`:

```python
from orchestration.full_plan_regenerator import regenerate_full_plan
from orchestration.pending_edits_repo import get_pending_edits, clear_all_pending
```

Route:

```python
@app.route("/api/plans/<plan_id>/regenerate-plan", methods=["POST"])
def api_regenerate_full_plan(plan_id: str):
    payload = request.get_json(silent=True) or {}
    force = bool(payload.get("force"))

    conn = db_conn()
    try:
        pv = get_plan(conn, plan_id)
        if pv is None:
            return jsonify({"ok": False, "error": "plan not found"}), 404

        edits = get_pending_edits(conn, plan_id)
        if not edits and not force:
            return jsonify({"ok": False,
                            "error": "No pending edits to apply. Pass force=true to regenerate anyway."}), 400

        concept_obj = pv.normalized_intake or pv.intake or {}
        existing_sections = (pv.plan or {}).get("sections") or []

        # Preserve existing image blocks by section so we don't regenerate images.
        existing_images: Dict[str, Any] = {}
        for sec in existing_sections:
            img = next((b for b in (sec.get("blocks") or [])
                        if b.get("type") == "image"), None)
            if img:
                existing_images[sec.get("id")] = img

        try:
            new_sections, applied_edit_ids = regenerate_full_plan(
                concept=concept_obj,
                existing_sections=existing_sections,
                pending_edits=edits,
                model_name=pv.model,
            )
        except ValueError as ve:
            return jsonify({"ok": False, "error": str(ve)}), 502
        except Exception as e:
            err_type = type(e).__name__
            msg = str(e) or err_type
            status = 429 if "RateLimit" in err_type else 502
            return jsonify({"ok": False, "error": f"{err_type}: {msg}",
                            "error_type": err_type}), status

        # Re-attach preserved images to their sections (insert at position 0).
        for sec in new_sections:
            img = existing_images.get(sec.get("id"))
            if img:
                blocks = [b for b in (sec.get("blocks") or [])
                          if b.get("type") != "image"]
                blocks.insert(0, img)
                sec["blocks"] = blocks

        # Build updated plan JSON and HTML.
        plan_data = dict(pv.plan or {})
        plan_data["sections"] = new_sections
        new_plan_html = render_template("plan_view.html", plan=plan_data)

        now = datetime.utcnow().isoformat() + "Z"
        conn.execute(
            """
            UPDATE plans
            SET plan_json = ?,
                plan_html = ?,
                stale_section_ids = NULL,
                pending_edits_json = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(plan_data, ensure_ascii=False),
             new_plan_html, now, plan_id),
        )
        conn.commit()

        # Record a revision per section.
        for sec in new_sections:
            sid = sec.get("id")
            comment = ("(full plan regen — edited: "
                       + ", ".join(applied_edit_ids) + ")") if sid in applied_edit_ids \
                      else "(full plan regen)"
            img = next((b for b in (sec.get("blocks") or [])
                        if b.get("type") == "image"), None)
            insert_revision(
                conn,
                plan_id=plan_id,
                section_id=sid,
                section_title=sec.get("title", sid),
                user_comment=comment,
                blocks=sec.get("blocks") or [],
                image_url=(img or {}).get("url"),
                image_alt=(img or {}).get("alt_text"),
            )

        return jsonify({
            "ok": True,
            "plan_html": new_plan_html,
            "applied_edit_section_ids": applied_edit_ids,
            "stale_section_ids": [],
        })
    finally:
        conn.close()
```

- [ ] **Step 4: PASS** (3 tests)

- [ ] **Step 5: Full suite passes**

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_regenerate_plan_endpoint.py
git commit -m "feat: POST /api/plans/<id>/regenerate-plan (full plan regen w/ pending edits)"
```

---

## Task 7: Rich edit modal + queue-vs-regen buttons

**Files:**
- Modify: `templates/plan_detail.html` — expand modal markup
- Modify: `static/css/section_edit.css` — editor styles
- Modify: `static/js/section_edit.js` — fetch current section, render block editors, save-to-queue

- [ ] **Step 1: Update modal markup in `templates/plan_detail.html`**

Replace the current modal body with a header, a dynamically-rendered block editor area, the existing comment box (renamed), and two buttons. Find the modal block and replace it with:

```html
<div class="edit-modal-backdrop" id="editModalBackdrop" hidden>
  <div class="edit-modal edit-modal-wide" role="dialog" aria-labelledby="editModalTitle" aria-modal="true">
    <div class="edit-modal-header">
      <h2 id="editModalTitle">Edit section</h2>
      <button type="button" class="edit-modal-close" id="editModalClose" aria-label="Close">×</button>
    </div>
    <div class="edit-modal-body">
      <div class="edit-modal-field">
        <label>Section</label>
        <input type="text" id="editSectionTitle" disabled />
      </div>
      <div class="edit-modal-field">
        <label>Current content (edit directly)</label>
        <div id="editBlocksContainer" class="edit-blocks-container"></div>
      </div>
      <div class="edit-modal-field">
        <label for="editUserComment">Additional guidance (optional)</label>
        <textarea id="editUserComment" rows="3"
          placeholder="Any extra direction for the AI when regenerating, e.g., 'shorter tone' or 'emphasize breakfast'."></textarea>
      </div>
      <div class="edit-modal-error" id="editModalError" hidden></div>
    </div>
    <div class="edit-modal-footer">
      <button type="button" class="btn btn-secondary" id="editModalCancel">Cancel</button>
      <button type="button" class="btn btn-secondary" id="editModalQueue">Save to queue</button>
      <button type="button" class="btn btn-primary" id="editModalSubmit">
        <span id="editModalSubmitLabel">Regenerate now</span>
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Append CSS**

In `static/css/section_edit.css` append:

```css
.edit-modal-wide { width: min(720px, 96vw); }

.edit-blocks-container { display: flex; flex-direction: column; gap: 12px; }

.edit-block {
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 8px;
  background: #fafafa;
  padding: 10px 12px;
}

.edit-block-header {
  font-size: 10px;
  font-weight: 700;
  color: #6b7a9a;
  text-transform: uppercase;
  letter-spacing: .5px;
  margin-bottom: 6px;
}

.edit-block textarea {
  width: 100%;
  min-height: 44px;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 6px;
  padding: 8px;
  font: inherit;
  font-size: 13px;
  resize: vertical;
}

.edit-bullet-row,
.edit-menu-item-row {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  margin-top: 4px;
}

.edit-bullet-row textarea,
.edit-menu-item-row textarea,
.edit-menu-item-row input {
  flex: 1;
}

.edit-bullet-row .btn-remove,
.edit-menu-item-row .btn-remove,
.edit-block-add {
  border: 1px solid var(--border, #d4d4d8);
  background: #fff;
  color: var(--text2, #27272a);
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  cursor: pointer;
}

.edit-block-add { margin-top: 4px; font-weight: 600; }
.edit-bullet-row .btn-remove:hover,
.edit-menu-item-row .btn-remove:hover { background: #fef2f2; border-color: #fecaca; color: #991b1b; }

.edit-block-table-ro {
  font-size: 12px;
  color: #525f7a;
  background: #fff;
  border: 1px dashed #d4d4d8;
  border-radius: 6px;
  padding: 8px;
}

.pending-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 700;
  color: #1e3a8a;
  background: #dbeafe;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: .3px;
}
```

- [ ] **Step 3: Rewrite `static/js/section_edit.js`**

Replace the current single-comment modal flow with a rich editor. Keep all existing helpers (`showToast`, `setRevertVisible`, `updateIframeAndScroll`) and extend them. Key additions:

```javascript
// ── Block editor state (per-open) ──────────────────────
let currentBlocks = [];           // live working copy of the block array
let currentOriginalBlocks = [];   // for reference only

function renderBlocksEditor() {
  const host = document.getElementById('editBlocksContainer');
  host.innerHTML = '';
  currentBlocks.forEach((block, i) => {
    host.appendChild(renderOneBlockEditor(block, i));
  });
}

function renderOneBlockEditor(block, idx) {
  const wrap = document.createElement('div');
  wrap.className = 'edit-block';
  const head = document.createElement('div');
  head.className = 'edit-block-header';
  head.textContent = block.type;
  wrap.appendChild(head);

  if (block.type === 'paragraph' || block.type === 'callout') {
    if (block.type === 'callout') {
      const t = document.createElement('input');
      t.value = block.title || '';
      t.placeholder = 'Title';
      t.oninput = () => { block.title = t.value; };
      wrap.appendChild(t);
    }
    const ta = document.createElement('textarea');
    ta.value = block.text || '';
    ta.rows = (block.type === 'callout') ? 3 : 5;
    ta.oninput = () => { block.text = ta.value; };
    wrap.appendChild(ta);
  } else if (block.type === 'bullets') {
    block.items = Array.isArray(block.items) ? block.items : [];
    const list = document.createElement('div');
    function drawBullets() {
      list.innerHTML = '';
      block.items.forEach((itm, bi) => {
        const row = document.createElement('div');
        row.className = 'edit-bullet-row';
        const ta = document.createElement('textarea');
        ta.rows = 1; ta.value = itm;
        ta.oninput = () => { block.items[bi] = ta.value; };
        const rm = document.createElement('button');
        rm.className = 'btn-remove'; rm.textContent = '×';
        rm.type = 'button';
        rm.onclick = () => { block.items.splice(bi, 1); drawBullets(); };
        row.appendChild(ta); row.appendChild(rm);
        list.appendChild(row);
      });
      const add = document.createElement('button');
      add.className = 'edit-block-add'; add.type = 'button';
      add.textContent = '+ Add bullet';
      add.onclick = () => { block.items.push(''); drawBullets(); };
      list.appendChild(add);
    }
    drawBullets();
    wrap.appendChild(list);
  } else if (block.type === 'menu_items') {
    block.items = Array.isArray(block.items) ? block.items : [];
    const catRow = document.createElement('input');
    catRow.placeholder = 'Category';
    catRow.value = block.category || '';
    catRow.oninput = () => { block.category = catRow.value; };
    wrap.appendChild(catRow);
    const list = document.createElement('div');
    function drawItems() {
      list.innerHTML = '';
      block.items.forEach((itm, bi) => {
        const row = document.createElement('div');
        row.className = 'edit-menu-item-row';
        const n = document.createElement('input'); n.placeholder = 'Name';
        n.value = itm.name || '';
        n.oninput = () => { block.items[bi].name = n.value; };
        const d = document.createElement('input'); d.placeholder = 'Description';
        d.value = itm.description || '';
        d.oninput = () => { block.items[bi].description = d.value; };
        const rm = document.createElement('button');
        rm.className = 'btn-remove'; rm.textContent = '×'; rm.type = 'button';
        rm.onclick = () => { block.items.splice(bi, 1); drawItems(); };
        row.appendChild(n); row.appendChild(d); row.appendChild(rm);
        list.appendChild(row);
      });
      const add = document.createElement('button');
      add.className = 'edit-block-add'; add.type = 'button';
      add.textContent = '+ Add item';
      add.onclick = () => { block.items.push({ name: '', description: '' }); drawItems(); };
      list.appendChild(add);
    }
    drawItems();
    wrap.appendChild(list);
  } else if (block.type === 'image' || block.type === 'table') {
    const ro = document.createElement('div');
    ro.className = 'edit-block-table-ro';
    ro.textContent = (block.type === 'image')
      ? 'Image blocks are preserved as-is. Re-upload via "Regenerate image" on a single-section edit.'
      : 'Tables cannot be edited inline in this version. Use "Regenerate now" with a comment.';
    wrap.appendChild(ro);
  } else {
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(block, null, 2);
    wrap.appendChild(pre);
  }

  return wrap;
}

async function fetchSectionBlocks(planId, sectionId) {
  // Use the existing plan_view by reading the iframe's plan_json via an inline fetch
  // Alternative: a dedicated endpoint — but the plan detail page already has the data.
  // We'll read from window.__CURRENT_PLAN_SECTIONS__ which plan_detail.html sets at load.
  const map = window.__CURRENT_PLAN_SECTIONS__ || {};
  const sec = map[sectionId];
  return sec ? JSON.parse(JSON.stringify(sec.blocks || [])) : [];
}
```

Modify the existing `openModal` to call `fetchSectionBlocks` and populate `currentBlocks`, then render the editor. Modify `submit()` to POST the blocks (not just the comment) to the existing `/regenerate` endpoint. Add a `queue()` handler for the new "Save to queue" button that PUTs to `/pending`.

- [ ] **Step 4: Pass section data to the template**

In `templates/plan_detail.html`, inject the section blocks map so JS can read them without a round-trip:

```html
<script>
  window.__CURRENT_PLAN_SECTIONS__ = {{ (plan.plan or {}).get('sections') | tojson | safe }}
    .reduce((acc, s) => { acc[s.id] = s; return acc; }, {});
</script>
```

Place this right before `<script src="/js/section_edit.js">`.

- [ ] **Step 5: Smoke-test in Flask dev**

Not covered by unit tests (UI), verify manually via `python app.py` → open a plan → Edit → blocks render in the modal.

- [ ] **Step 6: Commit**

```bash
git add templates/plan_detail.html static/css/section_edit.css static/js/section_edit.js
git commit -m "feat(ui): rich block editor in Edit modal, Save-to-queue + Regenerate-now"
```

---

## Task 8: Pending sidebar state + Regenerate Plan global button

**Files:**
- Modify: `templates/plan_detail.html` — pending badges + global button
- Modify: `static/css/section_edit.css` — (already done in Task 7 for `.pending-badge`)
- Modify: `static/js/section_edit.js` — global button handler, live sidebar sync
- Modify: `app.py` — pass `pending_section_ids` to the template context

- [ ] **Step 1: Update `app.py` template context**

In `plan_detail_route`, alongside `stale_section_ids` and `sections_with_history`, add:

```python
        pending_section_ids = set((plan.pending_edits or {}).keys())
```

Pass as kwarg to `render_template("plan_detail.html", ..., pending_section_ids=pending_section_ids)`.

- [ ] **Step 2: Sidebar changes in `templates/plan_detail.html`**

Above the existing section list inside `.section-list-panel`, add:

```html
<button
  type="button"
  class="btn btn-primary regen-plan-btn"
  id="regenPlanBtn"
  data-plan-id="{{ plan.id }}"
  {% if not pending_section_ids %}hidden{% endif %}
>
  ⚡ Regenerate Plan<span id="regenPlanCount">{% if pending_section_ids %} ({{ pending_section_ids|length }}){% endif %}</span>
</button>
```

Inside the per-section loop, add the Pending badge next to Stale:

```html
{% if section.id in (pending_section_ids or []) %}
  <span class="pending-badge" title="You have queued an edit for this section.">Pending</span>
{% endif %}
```

- [ ] **Step 3: CSS (global button)**

Append to `static/css/section_edit.css`:

```css
.regen-plan-btn {
  display: block;
  width: 100%;
  margin: 4px 0 14px;
  font-size: 13px;
  padding: 9px 14px;
  text-align: center;
}
.regen-plan-btn[hidden] { display: none; }
```

- [ ] **Step 4: JS — global regen handler**

In `static/js/section_edit.js`, add:

```javascript
function setPendingVisible(sectionId, visible) {
  const rows = document.querySelectorAll(`.section-row[data-section-id="${sectionId}"]`);
  rows.forEach((row) => {
    const actions = row.querySelector('.section-row-actions');
    const existing = actions.querySelector('.pending-badge');
    if (visible && !existing) {
      const b = document.createElement('span');
      b.className = 'pending-badge';
      b.title = 'You have queued an edit for this section.';
      b.textContent = 'Pending';
      actions.insertBefore(b, actions.firstChild);
    } else if (!visible && existing) {
      existing.remove();
    }
  });
}

function updateRegenPlanButton(pendingIds) {
  const btn = document.getElementById('regenPlanBtn');
  if (!btn) return;
  const count = (pendingIds || []).length;
  const countEl = document.getElementById('regenPlanCount');
  if (countEl) countEl.textContent = count ? ` (${count})` : '';
  if (count > 0) btn.removeAttribute('hidden');
  else btn.setAttribute('hidden', '');
}

async function regenerateFullPlan() {
  const btn = document.getElementById('regenPlanBtn');
  const planId = btn.dataset.planId;
  if (!confirm('Regenerate the full plan using your queued edits? This can take a few minutes and will cost an API call.')) return;
  btn.disabled = true;
  const originalText = btn.innerHTML;
  btn.textContent = 'Regenerating plan…';
  try {
    const resp = await fetch(`/api/plans/${encodeURIComponent(planId)}/regenerate-plan`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    let body;
    try { body = await resp.json(); } catch (_) { body = null; }
    if (!resp.ok || !body || !body.ok) {
      const msg = (body && (body.error || body.error_type)) || `Request failed (${resp.status}).`;
      showToast(`Regenerate failed: ${msg}`, 'error');
      return;
    }
    updateIframeAndScroll(body.plan_html, null);
    // Clear all Pending badges
    document.querySelectorAll('.pending-badge').forEach(b => b.remove());
    updateRegenPlanButton([]);
    // Clear all Stale badges (server cleared them too)
    document.querySelectorAll('.stale-badge').forEach(b => b.remove());
    showToast(`Plan regenerated — ${body.applied_edit_section_ids.length} edit(s) applied`);
  } catch (err) {
    showToast(`Network error: ${err.message || err}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

document.getElementById('regenPlanBtn')?.addEventListener('click', regenerateFullPlan);
```

After any successful save-to-queue (PUT `/pending`) also call `setPendingVisible(sid, true)` and `updateRegenPlanButton([...current + sid])`.

After any successful single-section regenerate or revert, call `setPendingVisible(sid, false)` and refetch via `/api/plans/<id>/pending` to resync (or just decrement). For simplicity, refetch:

```javascript
async function refetchPending(planId) {
  try {
    const resp = await fetch(`/api/plans/${encodeURIComponent(planId)}/pending`);
    const body = await resp.json();
    const ids = Object.keys(body.edits || {});
    document.querySelectorAll('.section-row').forEach(row => {
      setPendingVisible(row.dataset.sectionId, ids.includes(row.dataset.sectionId));
    });
    updateRegenPlanButton(ids);
  } catch (_) {}
}
```

Call `refetchPending(planId)` after queue save, after single regenerate, after revert.

- [ ] **Step 5: Smoke-test**

Open a plan, click Edit → Save to queue. Sidebar should show Pending badge + Regenerate Plan button. Click Regenerate Plan → confirm → wait → iframe refreshes, badges clear.

- [ ] **Step 6: Commit**

```bash
git add templates/plan_detail.html static/css/section_edit.css static/js/section_edit.js app.py
git commit -m "feat(ui): Pending badges, global Regenerate Plan button, live sidebar sync"
```

---

## Task 9: Manual E2E

- [ ] Open a plan → click Edit on mission → directly change "NYC pizza" to "Mediterranean bowls" in the paragraph text → Save to queue → sidebar shows Pending + Regenerate Plan.
- [ ] Click Edit on food_program → change menu direction text → Save to queue. Count should read "(2)".
- [ ] Click Regenerate Plan → confirm → wait 2–4 min. Plan re-renders with both edits baked in.
- [ ] Verify `section_revisions` has one row per section with comment like `"(full plan regen — edited: food_program, mission)"` for edited sections; `"(full plan regen)"` for the rest.
- [ ] Verify DB: `pending_edits_json` = NULL and `stale_section_ids` = NULL.

---

## Out of Scope (explicit)

- Per-edit diff view (user only sees the new version)
- Image regeneration during full-plan regen (images are preserved as-is; single-section flow still handles image regen)
- Table and callout inline edit for complex structures (basic support only; advanced tables stay read-only in v1)
- Undo of a full-plan regen (use the existing per-section Revert for fine-grained rollback)
