# Section Editing with Revisions & Stale-Flagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users edit any section of a generated plan by writing a natural-language comment (e.g., "make the tone more conservative"), regenerate just that section (with an optional image refresh), persist a full revision history, and visually flag downstream dependent sections as "may need regeneration" so the user knows what's potentially out of sync.

**Architecture:** A new `section_revisions` SQLite table stores every edit as an immutable row (plan_id, section_id, user_comment, blocks_json, image_url/alt, created_at); the latest revision per (plan_id, section_id) wins. A static dependency DAG in `orchestration/section_dependencies.py` declares which sections drift if a given section changes. A single-section regenerator reuses the bundle generator's system prompt but runs it scoped to one section spec, feeding user comment + existing-section context into the user prompt. A `POST /api/plans/<plan_id>/sections/<section_id>/regenerate` endpoint applies the new section to `plan_json`, re-renders `plan_html` via `plan_view.html`, updates a `stale_section_ids` JSON column on `plans`, and returns fresh state. The plan-detail UI gets a left sidebar listing sections with per-section Edit buttons and stale badges; the existing iframe preview is reloaded after each edit.

**Tech Stack:** Flask (existing), SQLite (existing), pydantic schemas (existing), OpenAI Responses API via `call_model_json` (existing), Jinja2 templates (existing), vanilla JS for the modal (no framework — matches repo style), pytest (bootstrapped in the image-prompts plan).

---

## Prerequisite

This plan assumes `2026-04-16-concept-specific-image-prompts.md` Task 1 (pytest bootstrap) has been merged, or executes that task first. If pytest isn't installed yet, run its Task 1 first.

---

## File Structure

**Create:**
- `orchestration/section_dependencies.py` — dependency DAG + downstream resolution
- `orchestration/revisions_repo.py` — CRUD for `section_revisions` table
- `orchestration/section_regenerator.py` — single-section regeneration against the LLM
- `tests/test_section_dependencies.py`
- `tests/test_revisions_repo.py`
- `tests/test_section_regenerator.py`
- `tests/test_regenerate_endpoint.py`
- `static/js/section_edit.js` — edit-modal interactions
- `static/css/section_edit.css` — modal + sidebar styling

**Modify:**
- `orchestration/db.py` — add `section_revisions` table and `stale_section_ids` column on `plans`
- `orchestration/plans_repo.py` — persist/read `stale_section_ids`; helper to swap a section in `plan_json`
- `schemas/plan_store_schema.py` — extend `PlanView` with `stale_section_ids`
- `app.py` — add regenerate endpoint; pass section list + stale set to `plan_detail.html`
- `templates/plan_detail.html` — sidebar, modal shell, JS/CSS includes

---

## Dependency Graph (draft, lives in `section_dependencies.py`)

Editing a key invalidates the values. Built from the `section_specs.py` content model:

| Edited section             | Downstream (marked stale)                                                                                              |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `concept_overview`         | `location_strategy`, `environment_atmosphere`, `brand_positioning`, `food_program`, `menu_structure`, `our_guests`, `swot`, `ownership_profile` |
| `location_strategy`        | `environment_atmosphere`, `our_guests`, `swot`                                                                         |
| `environment_atmosphere`   | `brand_positioning`                                                                                                    |
| `brand_positioning`        | `communications_strategy`, `digital_marketing`, `social_media`                                                         |
| `food_program`             | `menu_structure`, `menu_morning`, `menu_core_dayparts`, `menu_signature_items`, `menu_supporting_items`, `equipment_requirements` |
| `menu_structure`           | `menu_morning`, `menu_core_dayparts`, `menu_signature_items`, `menu_supporting_items`                                  |
| `beverage_program`         | `beverage_hot`, `beverage_non_alcoholic`, `beverage_alcohol`                                                           |
| `service_staffing_model`   | `operations_overview`, `pos_profitability_framework`                                                                   |
| `our_guests`               | `swot`                                                                                                                 |
| `daily_programming`        | (none)                                                                                                                 |
| all others                 | (none)                                                                                                                 |

Downstream is transitive: if A→B and B→C, editing A marks both B and C stale.

---

## Task 1: Schema migration — `section_revisions` table and `stale_section_ids` column

**Files:**
- Modify: `orchestration/db.py`

- [ ] **Step 1: Write failing test for schema presence**

Create `tests/test_db_migrations.py`:

```python
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
```

- [ ] **Step 2: Run, confirm it fails**

Run: `pytest tests/test_db_migrations.py -v`
Expected: both tests FAIL — table and column don't exist.

- [ ] **Step 3: Extend `SCHEMA_SQL` and add idempotent column-add**

In `orchestration/db.py`, replace the current contents with:

```python
# orchestration/db.py
import os
import sqlite3
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT,
  mode TEXT,
  locale TEXT,
  model TEXT,
  job_id TEXT,

  intake_json TEXT NOT NULL,
  normalized_intake_json TEXT,
  plan_json TEXT,
  plan_html TEXT,

  tokens_in INTEGER,
  tokens_out INTEGER,
  latency_ms INTEGER,
  error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_plans_created_at ON plans(created_at);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_job_id ON plans(job_id);

CREATE TABLE IF NOT EXISTS section_revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL,
  section_id TEXT NOT NULL,
  section_title TEXT NOT NULL,
  user_comment TEXT,
  blocks_json TEXT NOT NULL,
  image_url TEXT,
  image_alt TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sec_rev_plan ON section_revisions(plan_id);
CREATE INDEX IF NOT EXISTS idx_sec_rev_plan_section ON section_revisions(plan_id, section_id);
CREATE INDEX IF NOT EXISTS idx_sec_rev_created ON section_revisions(created_at);
"""


def ensure_instance_folder(instance_path: str) -> None:
    os.makedirs(instance_path, exist_ok=True)


def get_db_path(instance_path: str) -> str:
    return os.path.join(instance_path, "concept_lb.sqlite")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(instance_path: str) -> str:
    """Ensure folder + schema; applies idempotent column additions for legacy DBs."""
    ensure_instance_folder(instance_path)
    db_path = get_db_path(instance_path)

    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _add_column_if_missing(conn, "plans", "stale_section_ids", "TEXT")
        conn.commit()
    finally:
        conn.close()

    return db_path
```

- [ ] **Step 4: Run, verify both tests pass**

Run: `pytest tests/test_db_migrations.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestration/db.py tests/test_db_migrations.py
git commit -m "feat(db): add section_revisions table and stale_section_ids column"
```

---

## Task 2: Section dependency graph

**Files:**
- Create: `orchestration/section_dependencies.py`
- Create: `tests/test_section_dependencies.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_section_dependencies.py`:

```python
from orchestration.section_dependencies import downstream_of


def test_concept_overview_invalidates_many():
    stale = downstream_of("concept_overview")
    assert "location_strategy" in stale
    assert "brand_positioning" in stale
    assert "menu_structure" in stale
    assert "menu_core_dayparts" in stale  # transitive via menu_structure
    # It should not include itself
    assert "concept_overview" not in stale


def test_menu_structure_transitive_to_menu_children():
    stale = downstream_of("menu_structure")
    assert stale == {
        "menu_morning",
        "menu_core_dayparts",
        "menu_signature_items",
        "menu_supporting_items",
    }


def test_daily_programming_has_no_dependents():
    assert downstream_of("daily_programming") == set()


def test_unknown_section_returns_empty_set():
    assert downstream_of("nonexistent_section") == set()


def test_food_program_cascades_to_menus_and_equipment():
    stale = downstream_of("food_program")
    assert "menu_structure" in stale
    assert "menu_signature_items" in stale  # via menu_structure
    assert "equipment_requirements" in stale
```

- [ ] **Step 2: Run, confirm failures**

Run: `pytest tests/test_section_dependencies.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the graph**

Create `orchestration/section_dependencies.py`:

```python
from typing import Dict, Set


# Direct (non-transitive) dependents. Key = edited section, value = sections
# that should be flagged stale because their generated content references
# or builds on the key.
DIRECT_DEPENDENTS: Dict[str, Set[str]] = {
    "concept_overview": {
        "location_strategy",
        "environment_atmosphere",
        "brand_positioning",
        "food_program",
        "menu_structure",
        "our_guests",
        "swot",
        "ownership_profile",
    },
    "location_strategy": {
        "environment_atmosphere",
        "our_guests",
        "swot",
    },
    "environment_atmosphere": {
        "brand_positioning",
    },
    "brand_positioning": {
        "communications_strategy",
        "digital_marketing",
        "social_media",
    },
    "food_program": {
        "menu_structure",
        "menu_morning",
        "menu_core_dayparts",
        "menu_signature_items",
        "menu_supporting_items",
        "equipment_requirements",
    },
    "menu_structure": {
        "menu_morning",
        "menu_core_dayparts",
        "menu_signature_items",
        "menu_supporting_items",
    },
    "beverage_program": {
        "beverage_hot",
        "beverage_non_alcoholic",
        "beverage_alcohol",
    },
    "service_staffing_model": {
        "operations_overview",
        "pos_profitability_framework",
    },
    "our_guests": {
        "swot",
    },
}


def downstream_of(section_id: str) -> Set[str]:
    """Return the transitive closure of sections that become stale when
    `section_id` is edited. Does not include `section_id` itself."""
    stale: Set[str] = set()
    frontier = list(DIRECT_DEPENDENTS.get(section_id, set()))
    while frontier:
        current = frontier.pop()
        if current in stale:
            continue
        stale.add(current)
        frontier.extend(DIRECT_DEPENDENTS.get(current, set()))
    return stale
```

- [ ] **Step 4: Run, verify all pass**

Run: `pytest tests/test_section_dependencies.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestration/section_dependencies.py tests/test_section_dependencies.py
git commit -m "feat: add section dependency graph with transitive closure"
```

---

## Task 3: Revisions repo

**Files:**
- Create: `orchestration/revisions_repo.py`
- Create: `tests/test_revisions_repo.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_revisions_repo.py`:

```python
import json
from datetime import datetime, timezone

import pytest

from orchestration.db import connect, init_db
from orchestration.revisions_repo import (
    insert_revision,
    latest_revisions_by_section,
    revisions_for_section,
)


@pytest.fixture
def db(tmp_path):
    db_path = init_db(str(tmp_path))
    conn = connect(db_path)
    # Seed a plan row so the FK is satisfied
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO plans (id, created_at, updated_at, status, intake_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("plan-1", now, now, "complete", "{}"),
    )
    conn.commit()
    yield conn
    conn.close()


def test_insert_and_read_single_revision(db):
    insert_revision(
        db,
        plan_id="plan-1",
        section_id="mission",
        section_title="Mission",
        user_comment="Make it shorter.",
        blocks=[{"type": "paragraph", "text": "Short mission."}],
        image_url=None,
        image_alt=None,
    )

    revs = revisions_for_section(db, plan_id="plan-1", section_id="mission")
    assert len(revs) == 1
    assert revs[0].user_comment == "Make it shorter."
    assert revs[0].blocks == [{"type": "paragraph", "text": "Short mission."}]


def test_latest_by_section_returns_newest_per_section(db):
    insert_revision(
        db,
        plan_id="plan-1",
        section_id="mission",
        section_title="Mission",
        user_comment="v1",
        blocks=[{"type": "paragraph", "text": "v1"}],
        image_url=None,
        image_alt=None,
    )
    insert_revision(
        db,
        plan_id="plan-1",
        section_id="mission",
        section_title="Mission",
        user_comment="v2",
        blocks=[{"type": "paragraph", "text": "v2"}],
        image_url=None,
        image_alt=None,
    )
    insert_revision(
        db,
        plan_id="plan-1",
        section_id="vision",
        section_title="Vision",
        user_comment="only",
        blocks=[{"type": "paragraph", "text": "only"}],
        image_url=None,
        image_alt=None,
    )

    latest = latest_revisions_by_section(db, plan_id="plan-1")
    assert set(latest.keys()) == {"mission", "vision"}
    assert latest["mission"].user_comment == "v2"
    assert latest["vision"].user_comment == "only"


def test_insert_rejects_missing_plan(db):
    # FK should reject unknown plan_id
    with pytest.raises(Exception):
        insert_revision(
            db,
            plan_id="nope",
            section_id="mission",
            section_title="Mission",
            user_comment="x",
            blocks=[],
            image_url=None,
            image_alt=None,
        )
```

- [ ] **Step 2: Run, confirm failures**

Run: `pytest tests/test_revisions_repo.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the repo**

Create `orchestration/revisions_repo.py`:

```python
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class SectionRevision:
    id: int
    plan_id: str
    section_id: str
    section_title: str
    user_comment: Optional[str]
    blocks: List[Dict[str, Any]]
    image_url: Optional[str]
    image_alt: Optional[str]
    created_at: str


def _row_to_revision(row: sqlite3.Row) -> SectionRevision:
    return SectionRevision(
        id=row["id"],
        plan_id=row["plan_id"],
        section_id=row["section_id"],
        section_title=row["section_title"],
        user_comment=row["user_comment"],
        blocks=json.loads(row["blocks_json"]),
        image_url=row["image_url"],
        image_alt=row["image_alt"],
        created_at=row["created_at"],
    )


def insert_revision(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    section_id: str,
    section_title: str,
    user_comment: Optional[str],
    blocks: List[Dict[str, Any]],
    image_url: Optional[str],
    image_alt: Optional[str],
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO section_revisions
          (plan_id, section_id, section_title, user_comment,
           blocks_json, image_url, image_alt, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            section_id,
            section_title,
            user_comment,
            json.dumps(blocks, ensure_ascii=False),
            image_url,
            image_alt,
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def revisions_for_section(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    section_id: str,
) -> List[SectionRevision]:
    rows = conn.execute(
        """
        SELECT * FROM section_revisions
        WHERE plan_id = ? AND section_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (plan_id, section_id),
    ).fetchall()
    return [_row_to_revision(r) for r in rows]


def latest_revisions_by_section(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
) -> Dict[str, SectionRevision]:
    """Map section_id -> newest revision for this plan."""
    rows = conn.execute(
        """
        SELECT r.*
        FROM section_revisions r
        INNER JOIN (
            SELECT section_id, MAX(id) AS max_id
            FROM section_revisions
            WHERE plan_id = ?
            GROUP BY section_id
        ) latest
          ON r.id = latest.max_id
        """,
        (plan_id,),
    ).fetchall()
    return {r["section_id"]: _row_to_revision(r) for r in rows}
```

- [ ] **Step 4: Run, verify all pass**

Run: `pytest tests/test_revisions_repo.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestration/revisions_repo.py tests/test_revisions_repo.py
git commit -m "feat: add section revisions repository with latest-per-section lookup"
```

---

## Task 4: Single-section regenerator

**Files:**
- Create: `orchestration/section_regenerator.py`
- Create: `tests/test_section_regenerator.py`

- [ ] **Step 1: Write failing test for regeneration**

Create `tests/test_section_regenerator.py`:

```python
from unittest.mock import patch

import pytest

from orchestration.section_regenerator import regenerate_section


def _fake_llm_response():
    return {
        "sections": [
            {
                "id": "mission",
                "title": "Mission",
                "blocks": [
                    {"type": "paragraph", "text": "A tighter, more conservative mission."},
                    {"type": "bullets", "items": ["clear", "concise"]},
                ],
            }
        ]
    }


def _existing_section():
    return {
        "id": "mission",
        "title": "Mission",
        "blocks": [
            {"type": "paragraph", "text": "Original verbose mission statement."},
            {"type": "bullets", "items": ["verbose", "rambly"]},
        ],
    }


def test_regenerate_returns_new_section_and_passes_user_comment(fake_concept):
    with patch(
        "orchestration.section_regenerator.call_model_json",
        return_value=_fake_llm_response(),
    ) as mocked:
        new_section = regenerate_section(
            concept=fake_concept,
            section_id="mission",
            existing_section=_existing_section(),
            user_comment="Make it shorter and more conservative.",
        )

    assert new_section["id"] == "mission"
    assert new_section["title"] == "Mission"
    blocks = new_section["blocks"]
    assert blocks[0]["type"] == "paragraph"
    assert "conservative" in blocks[0]["text"]

    # User prompt carries both the user comment and the existing section JSON
    _, kwargs = mocked.call_args
    up = kwargs["user_prompt"]
    assert "Make it shorter and more conservative." in up
    assert "Original verbose mission statement." in up


def test_regenerate_raises_when_llm_returns_wrong_section_id(fake_concept):
    bad_response = {
        "sections": [
            {"id": "vision", "title": "Vision", "blocks": [{"type": "paragraph", "text": "x"}]}
        ]
    }
    with patch(
        "orchestration.section_regenerator.call_model_json",
        return_value=bad_response,
    ):
        with pytest.raises(ValueError, match="did not return section 'mission'"):
            regenerate_section(
                concept=fake_concept,
                section_id="mission",
                existing_section=_existing_section(),
                user_comment="x",
            )


def test_regenerate_raises_when_required_blocks_missing(fake_concept):
    bad_response = {
        "sections": [
            {"id": "mission", "title": "Mission", "blocks": [{"type": "paragraph", "text": "only paragraph"}]}
        ]
    }
    with patch(
        "orchestration.section_regenerator.call_model_json",
        return_value=bad_response,
    ):
        with pytest.raises(ValueError, match="missing required block"):
            regenerate_section(
                concept=fake_concept,
                section_id="mission",
                existing_section=_existing_section(),
                user_comment="x",
            )


def test_regenerate_raises_for_unknown_section_id(fake_concept):
    with pytest.raises(KeyError):
        regenerate_section(
            concept=fake_concept,
            section_id="not_a_real_section",
            existing_section=None,
            user_comment="x",
        )
```

- [ ] **Step 2: Run, confirm failures**

Run: `pytest tests/test_section_regenerator.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement regenerator**

Create `orchestration/section_regenerator.py`:

```python
import json
from typing import Any, Dict, Optional

from orchestration.openai_client import call_model_json
from orchestration.section_bundle_generator import (
    BUNDLE_SYSTEM_PROMPT,
    _validate_required_blocks,
)
from orchestration.section_specs import SECTION_SPECS


_REGEN_USER_TEMPLATE = """
CONCEPT_OBJECT (JSON):
{concept_json}

SECTION_SPEC (single-section mode):
{spec_json}

EXISTING_SECTION (what the reader currently sees; JSON):
{existing_section_json}

USER_EDIT_COMMENT:
\"\"\"{user_comment}\"\"\"

INSTRUCTIONS:
- Regenerate ONLY the single section described in SECTION_SPEC.
- Apply the USER_EDIT_COMMENT as steering: respect the user's requested
  changes in tone, emphasis, length, or content.
- If EXISTING_SECTION is provided, preserve anything the user didn't
  explicitly ask to change.
- Output must match the normal bundle shape with exactly ONE section:

{{
  "sections": [
    {{
      "id": "...",
      "title": "...",
      "blocks": [ ... ]
    }}
  ]
}}

- `id` and `title` MUST match SECTION_SPEC exactly.
- Include ALL required_blocks listed in SECTION_SPEC.
- Do NOT include assumptions_table or disclaimer.
- Do NOT include any other sections.
""".strip()


_REGEN_MODEL = "gpt-5.2"
_REGEN_MAX_TOKENS = 4000


def _find_spec(section_id: str) -> Dict[str, Any]:
    for spec in SECTION_SPECS:
        if spec["id"] == section_id:
            return spec
    raise KeyError(f"Unknown section_id: {section_id!r}")


def regenerate_section(
    *,
    concept: Dict[str, Any],
    section_id: str,
    existing_section: Optional[Dict[str, Any]],
    user_comment: str,
) -> Dict[str, Any]:
    """Regenerate a single section with a steering user comment.

    Raises:
        KeyError: if section_id is not a known section.
        ValueError: if the LLM returns the wrong section or misses required blocks.
    """
    spec = _find_spec(section_id)

    user_prompt = _REGEN_USER_TEMPLATE.format(
        concept_json=json.dumps(concept, ensure_ascii=False),
        spec_json=json.dumps(spec, ensure_ascii=False),
        existing_section_json=(
            json.dumps(existing_section, ensure_ascii=False)
            if existing_section is not None else "null"
        ),
        user_comment=user_comment or "",
    )

    result = call_model_json(
        system_prompt=BUNDLE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_name=_REGEN_MODEL,
        max_output_tokens=_REGEN_MAX_TOKENS,
    )

    sections = result.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError(f"Regenerator response had no sections: {result!r}")

    new_section = sections[0]
    if new_section.get("id") != section_id:
        raise ValueError(
            f"Regenerator did not return section {section_id!r}; got {new_section.get('id')!r}"
        )

    _validate_required_blocks(spec, new_section)
    return new_section
```

- [ ] **Step 4: Run, verify all pass**

Run: `pytest tests/test_section_regenerator.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestration/section_regenerator.py tests/test_section_regenerator.py
git commit -m "feat: single-section regenerator driven by user comment"
```

---

## Task 5: Plans repo helpers for swapping a section and updating stale set

**Files:**
- Modify: `orchestration/plans_repo.py`

- [ ] **Step 1: Write failing test for swap + persist**

Create `tests/test_plans_repo_swap.py`:

```python
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
```

- [ ] **Step 2: Run, confirm failures**

Run: `pytest tests/test_plans_repo_swap.py -v`
Expected: FAIL — `apply_section_update` doesn't exist yet, `get_plan` doesn't return `stale_section_ids`.

- [ ] **Step 3: Update `schemas/plan_store_schema.py`**

Find the `PlanView` pydantic model in `schemas/plan_store_schema.py` and add a field. If the file uses `BaseModel`, add:

```python
stale_section_ids: list[str] = Field(default_factory=list)
```

(Import `Field` from pydantic if not already imported.) Keep all other fields as-is.

- [ ] **Step 4: Update `orchestration/plans_repo.py`**

Extend `orchestration/plans_repo.py` with:

1. Read `stale_section_ids` in `get_plan` — in the `SELECT *` path, parse the new column into a list.
2. Add new `apply_section_update` function.

Replace `get_plan` with:

```python
def get_plan(conn: sqlite3.Connection, plan_id: str) -> Optional[PlanView]:
    r = conn.execute(
        """
        SELECT *
        FROM plans
        WHERE id = ?
        """,
        (plan_id,),
    ).fetchone()

    if not r:
        return None

    stale_ids_raw = r["stale_section_ids"] if "stale_section_ids" in r.keys() else None
    stale_ids: list = []
    if stale_ids_raw:
        try:
            parsed = json.loads(stale_ids_raw)
            if isinstance(parsed, list):
                stale_ids = [str(x) for x in parsed]
        except Exception:
            stale_ids = []

    return PlanView(
        id=r["id"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        status=r["status"],
        title=r["title"],
        mode=r["mode"],
        locale=r["locale"],
        model=r["model"],
        job_id=r["job_id"],
        intake=_json_loads_safe(r["intake_json"]) or {},
        normalized_intake=_json_loads_safe(r["normalized_intake_json"]),
        plan=_json_loads_safe(r["plan_json"]),
        plan_html=r["plan_html"],
        tokens_in=r["tokens_in"],
        tokens_out=r["tokens_out"],
        latency_ms=r["latency_ms"],
        error_message=r["error_message"],
        stale_section_ids=stale_ids,
    )
```

Append to `orchestration/plans_repo.py`:

```python
from datetime import datetime, timezone
from typing import Iterable


def apply_section_update(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    new_section: Dict[str, Any],
    new_plan_html: str,
    stale_section_ids: Iterable[str],
) -> None:
    """Replace one section in plan_json, persist updated plan_html, and
    overwrite the stale_section_ids set.

    Raises ValueError if the plan doesn't exist.
    """
    row = conn.execute(
        "SELECT plan_json FROM plans WHERE id = ?", (plan_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"plan not found: {plan_id!r}")

    plan = json.loads(row["plan_json"] or "{}")
    sections = plan.get("sections") or []
    target_id = new_section.get("id")
    replaced = False
    for idx, sec in enumerate(sections):
        if sec.get("id") == target_id:
            sections[idx] = new_section
            replaced = True
            break
    if not replaced:
        # New section edit targeting a section the plan never had; append
        sections.append(new_section)
    plan["sections"] = sections

    stale_json = json.dumps(sorted({str(s) for s in stale_section_ids}))
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        UPDATE plans
        SET plan_json = ?,
            plan_html = ?,
            stale_section_ids = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            json.dumps(plan, ensure_ascii=False),
            new_plan_html,
            stale_json,
            now,
            plan_id,
        ),
    )
    conn.commit()
```

- [ ] **Step 5: Run, verify all pass**

Run: `pytest tests/test_plans_repo_swap.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add orchestration/plans_repo.py schemas/plan_store_schema.py tests/test_plans_repo_swap.py
git commit -m "feat: apply_section_update + stale_section_ids readback in plans_repo"
```

---

## Task 6: Regenerate API endpoint

**Files:**
- Modify: `app.py`
- Create: `tests/test_regenerate_endpoint.py`

- [ ] **Step 1: Write failing endpoint test**

Create `tests/test_regenerate_endpoint.py`:

```python
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
```

- [ ] **Step 2: Run, confirm failures**

Run: `pytest tests/test_regenerate_endpoint.py -v`
Expected: FAIL — endpoint not registered.

- [ ] **Step 3: Implement the endpoint in `app.py`**

Near the other `/api/plans/...` routes in `app.py`, add imports at the top:

```python
from orchestration.section_regenerator import regenerate_section
from orchestration.section_dependencies import downstream_of
from orchestration.revisions_repo import insert_revision, latest_revisions_by_section
from orchestration.plans_repo import apply_section_update
from orchestration.image_generator import generate_section_images
```

Add the route (place it near other plan-detail API routes):

```python
@app.route("/api/plans/<plan_id>/sections/<section_id>/regenerate", methods=["POST"])
def api_regenerate_section(plan_id: str, section_id: str):
    payload = request.get_json(silent=True) or {}
    user_comment = (payload.get("user_comment") or "").strip()
    regenerate_image_flag = bool(payload.get("regenerate_image"))

    conn = db_conn()
    try:
        plan_view = get_plan(conn, plan_id)
        if plan_view is None:
            return jsonify({"ok": False, "error": "plan not found"}), 404

        plan_data = plan_view.plan or {}
        existing_sections = plan_data.get("sections") or []
        existing_section = next(
            (s for s in existing_sections if s.get("id") == section_id),
            None,
        )

        concept_obj = plan_view.normalized_intake or plan_view.intake or {}

        # Regenerate the section content
        try:
            new_section = regenerate_section(
                concept=concept_obj,
                section_id=section_id,
                existing_section=existing_section,
                user_comment=user_comment,
            )
        except KeyError:
            return jsonify({"ok": False, "error": f"unknown section: {section_id}"}), 400
        except ValueError as ve:
            return jsonify({"ok": False, "error": str(ve)}), 502

        # Optionally regenerate the image
        new_image_url = None
        new_image_alt = None
        if regenerate_image_flag:
            img = generate_section_images(
                concept_name=concept_obj.get("concept_name", "Restaurant Concept"),
                concept_description=concept_obj.get("one_liner", "") or concept_obj.get("concept_description", ""),
                section_id=section_id,
                section_title=new_section.get("title", section_id),
                concept=concept_obj,
            )
            if img:
                new_image_url, new_image_alt = img
                # Insert image block at start of section
                image_block = {
                    "type": "image",
                    "url": new_image_url,
                    "alt_text": new_image_alt,
                    "caption": f"Visual representation: {new_section.get('title', '')}",
                }
                blocks = list(new_section.get("blocks") or [])
                # Strip any old image block first
                blocks = [b for b in blocks if b.get("type") != "image"]
                blocks.insert(0, image_block)
                new_section["blocks"] = blocks
        else:
            # Preserve existing image if there was one
            if existing_section:
                existing_image_block = next(
                    (b for b in (existing_section.get("blocks") or []) if b.get("type") == "image"),
                    None,
                )
                if existing_image_block:
                    blocks = list(new_section.get("blocks") or [])
                    blocks = [b for b in blocks if b.get("type") != "image"]
                    blocks.insert(0, existing_image_block)
                    new_section["blocks"] = blocks
                    new_image_url = existing_image_block.get("url")
                    new_image_alt = existing_image_block.get("alt_text")

        # Compute new stale set: existing stale minus the regenerated one,
        # plus the transitive downstream of the regenerated section.
        previous_stale = set(plan_view.stale_section_ids or [])
        previous_stale.discard(section_id)
        new_stale = previous_stale | downstream_of(section_id)
        new_stale.discard(section_id)

        # Swap the section into plan_json
        plan_data_updated = dict(plan_data)
        plan_data_updated["sections"] = [
            new_section if s.get("id") == section_id else s
            for s in existing_sections
        ]
        # If somehow the section didn't exist before, append
        if not any(s.get("id") == section_id for s in existing_sections):
            plan_data_updated["sections"] = list(existing_sections) + [new_section]

        # Re-render HTML from updated plan_json
        new_plan_html = render_template("plan_view.html", plan=plan_data_updated)

        # Persist: plan_json, plan_html, stale set
        apply_section_update(
            conn,
            plan_id=plan_id,
            new_section=new_section,
            new_plan_html=new_plan_html,
            stale_section_ids=new_stale,
        )

        # Audit: persist the revision
        insert_revision(
            conn,
            plan_id=plan_id,
            section_id=section_id,
            section_title=new_section.get("title", section_id),
            user_comment=user_comment or None,
            blocks=new_section.get("blocks") or [],
            image_url=new_image_url,
            image_alt=new_image_alt,
        )

        return jsonify({
            "ok": True,
            "section": new_section,
            "plan_html": new_plan_html,
            "stale_section_ids": sorted(new_stale),
        })
    finally:
        conn.close()
```

- [ ] **Step 4: Run endpoint tests, verify all pass**

Run: `pytest tests/test_regenerate_endpoint.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Run full suite, verify no regressions**

Run: `pytest -v`
Expected: all tests across all files PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_regenerate_endpoint.py
git commit -m "feat: POST /api/plans/<id>/sections/<id>/regenerate endpoint"
```

---

## Task 7: Plan-detail sidebar with section list and stale badges

**Files:**
- Modify: `app.py` — pass section list + stale set into template
- Modify: `templates/plan_detail.html`
- Create: `static/css/section_edit.css`

- [ ] **Step 1: Locate the plan detail route in `app.py`**

Find the route that renders `plan_detail.html` (search for `render_template("plan_detail.html"`). In that handler, load the plan and inject `sections` and `stale_section_ids` into the template context.

Example shape (adjust to match existing handler):

```python
@app.route("/plans/<plan_id>")
def plan_detail_page(plan_id: str):
    conn = db_conn()
    try:
        view = get_plan(conn, plan_id)
    finally:
        conn.close()
    if view is None:
        return redirect("/plans")

    sections_summary = []
    for sec in (view.plan or {}).get("sections") or []:
        sections_summary.append({
            "id": sec.get("id"),
            "title": sec.get("title"),
        })

    return render_template(
        "plan_detail.html",
        plan=view,
        sections=sections_summary,
        stale_section_ids=view.stale_section_ids or [],
    )
```

(If the route already exists, add the three new kwargs to `render_template`.)

- [ ] **Step 2: Create the sidebar CSS**

Create `static/css/section_edit.css`:

```css
.section-list-panel {
  position: fixed;
  top: 56px;
  left: 0;
  bottom: 0;
  width: 280px;
  background: var(--bg2, #f4f4f5);
  border-right: 1px solid var(--border, #d4d4d8);
  overflow-y: auto;
  padding: 16px 12px;
  z-index: 50;
}

.section-list-panel h3 {
  font-size: 11px;
  font-weight: 700;
  color: var(--dim, #a1a1aa);
  text-transform: uppercase;
  letter-spacing: .5px;
  margin: 4px 8px 10px;
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: default;
  transition: background .15s ease;
}

.section-row:hover {
  background: var(--surface, #e4e4e7);
}

.section-row-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text2, #27272a);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-row-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.stale-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 700;
  color: #92400e;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: .3px;
}

.edit-section-btn {
  border: 1px solid var(--border, #d4d4d8);
  background: #fff;
  color: var(--text2, #27272a);
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all .15s ease;
}

.edit-section-btn:hover {
  background: var(--surface, #e4e4e7);
  border-color: var(--border2, #a1a1aa);
}

/* Push main content right to make room for the sidebar */
body.with-section-sidebar .chrome-inner,
body.with-section-sidebar .stats-bar,
body.with-section-sidebar .content {
  margin-left: 280px;
}
```

- [ ] **Step 3: Modify `templates/plan_detail.html` to render the sidebar**

Open `templates/plan_detail.html`. In the `<head>` add:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/section_edit.css') }}">
```

On the `<body>` tag, add the class:

```html
<body class="with-section-sidebar">
```

Immediately inside `<body>`, before the existing chrome, add:

```html
<aside class="section-list-panel">
  <h3>Plan sections</h3>
  {% for section in sections or [] %}
    <div class="section-row" data-section-id="{{ section.id }}">
      <div class="section-row-title" title="{{ section.title }}">
        {{ section.title }}
      </div>
      <div class="section-row-actions">
        {% if section.id in (stale_section_ids or []) %}
          <span class="stale-badge" title="This section may be out of date. Review or regenerate.">Stale</span>
        {% endif %}
        <button
          type="button"
          class="edit-section-btn"
          data-section-id="{{ section.id }}"
          data-section-title="{{ section.title }}"
          data-plan-id="{{ plan.id }}"
        >Edit</button>
      </div>
    </div>
  {% endfor %}
</aside>
```

- [ ] **Step 4: Start the server and verify the sidebar renders**

Run: `python app.py`
In a browser, open any existing plan detail page.
Expected: a left sidebar lists every section with an Edit button. Sections flagged stale (if any in DB) show a yellow "Stale" badge.

- [ ] **Step 5: Commit**

```bash
git add app.py templates/plan_detail.html static/css/section_edit.css
git commit -m "feat(ui): add plan-detail section sidebar with edit buttons and stale badges"
```

---

## Task 8: Edit modal + JS wiring

**Files:**
- Create: `static/js/section_edit.js`
- Modify: `templates/plan_detail.html`

- [ ] **Step 1: Create the modal markup**

In `templates/plan_detail.html`, just before the closing `</body>`, add:

```html
<div class="edit-modal-backdrop" id="editModalBackdrop" hidden>
  <div class="edit-modal" role="dialog" aria-labelledby="editModalTitle" aria-modal="true">
    <div class="edit-modal-header">
      <h2 id="editModalTitle">Edit section</h2>
      <button type="button" class="edit-modal-close" id="editModalClose" aria-label="Close">×</button>
    </div>
    <div class="edit-modal-body">
      <div class="edit-modal-field">
        <label for="editSectionTitle">Section</label>
        <input type="text" id="editSectionTitle" disabled />
      </div>
      <div class="edit-modal-field">
        <label for="editUserComment">What would you like to change?</label>
        <textarea id="editUserComment" rows="6"
          placeholder="e.g., Make the tone more conservative. Emphasize the breakfast program. Remove the reference to X."></textarea>
      </div>
      <div class="edit-modal-field checkbox-row">
        <label>
          <input type="checkbox" id="editRegenerateImage" />
          Regenerate the section image
        </label>
      </div>
      <div class="edit-modal-error" id="editModalError" hidden></div>
    </div>
    <div class="edit-modal-footer">
      <button type="button" class="btn btn-secondary" id="editModalCancel">Cancel</button>
      <button type="button" class="btn btn-primary" id="editModalSubmit">
        <span id="editModalSubmitLabel">Regenerate</span>
      </button>
    </div>
  </div>
</div>
<script src="{{ url_for('static', filename='js/section_edit.js') }}"></script>
```

- [ ] **Step 2: Extend `static/css/section_edit.css` with modal styles**

Append to `static/css/section_edit.css`:

```css
.edit-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.edit-modal-backdrop[hidden] { display: none; }

.edit-modal {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.25);
  width: min(560px, 94vw);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.edit-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border, #d4d4d8);
}

.edit-modal-header h2 {
  font-size: 16px;
  font-weight: 700;
}

.edit-modal-close {
  background: transparent;
  border: none;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  color: var(--dim, #a1a1aa);
  padding: 4px 8px;
}

.edit-modal-body {
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.edit-modal-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text2, #27272a);
  margin-bottom: 6px;
}

.edit-modal-field input[type="text"],
.edit-modal-field textarea {
  width: 100%;
  padding: 10px 12px;
  font: inherit;
  font-size: 13px;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 8px;
  background: #fff;
  color: var(--text, #09090b);
}

.edit-modal-field textarea {
  resize: vertical;
  min-height: 120px;
}

.edit-modal-field.checkbox-row label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
}

.edit-modal-error {
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  font-size: 12px;
}

.edit-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--border, #d4d4d8);
  background: var(--bg2, #f4f4f5);
}

.edit-modal-footer .btn[disabled] {
  opacity: .55;
  cursor: not-allowed;
}
```

- [ ] **Step 3: Implement the JS**

Create `static/js/section_edit.js`:

```javascript
(function () {
  'use strict';

  const backdrop = document.getElementById('editModalBackdrop');
  const titleInput = document.getElementById('editSectionTitle');
  const commentInput = document.getElementById('editUserComment');
  const imageCheckbox = document.getElementById('editRegenerateImage');
  const errorBox = document.getElementById('editModalError');
  const submitBtn = document.getElementById('editModalSubmit');
  const submitLabel = document.getElementById('editModalSubmitLabel');
  const cancelBtn = document.getElementById('editModalCancel');
  const closeBtn = document.getElementById('editModalClose');

  let currentPlanId = null;
  let currentSectionId = null;

  function openModal({ planId, sectionId, sectionTitle }) {
    currentPlanId = planId;
    currentSectionId = sectionId;
    titleInput.value = sectionTitle;
    commentInput.value = '';
    imageCheckbox.checked = false;
    errorBox.hidden = true;
    errorBox.textContent = '';
    submitBtn.disabled = false;
    submitLabel.textContent = 'Regenerate';
    backdrop.hidden = false;
    setTimeout(() => commentInput.focus(), 10);
  }

  function closeModal() {
    backdrop.hidden = true;
    currentPlanId = null;
    currentSectionId = null;
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  async function submit() {
    const comment = commentInput.value.trim();
    if (!comment) {
      showError('Please describe what you want to change.');
      return;
    }
    submitBtn.disabled = true;
    submitLabel.textContent = 'Regenerating…';
    errorBox.hidden = true;

    try {
      const resp = await fetch(
        `/api/plans/${encodeURIComponent(currentPlanId)}/sections/${encodeURIComponent(currentSectionId)}/regenerate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_comment: comment,
            regenerate_image: imageCheckbox.checked,
          }),
        },
      );
      const body = await resp.json();
      if (!resp.ok || !body.ok) {
        showError(body.error || `Request failed (${resp.status}).`);
        submitBtn.disabled = false;
        submitLabel.textContent = 'Regenerate';
        return;
      }

      // Update the iframe preview in place
      const frame = document.getElementById('previewFrame');
      if (frame) {
        frame.srcdoc = body.plan_html;
      }

      // Update stale badges in the sidebar
      const staleSet = new Set(body.stale_section_ids || []);
      document.querySelectorAll('.section-row').forEach((row) => {
        const sid = row.dataset.sectionId;
        const actions = row.querySelector('.section-row-actions');
        const existingBadge = actions.querySelector('.stale-badge');
        const shouldHaveBadge = staleSet.has(sid);
        if (shouldHaveBadge && !existingBadge) {
          const badge = document.createElement('span');
          badge.className = 'stale-badge';
          badge.title = 'This section may be out of date. Review or regenerate.';
          badge.textContent = 'Stale';
          actions.insertBefore(badge, actions.firstChild);
        } else if (!shouldHaveBadge && existingBadge) {
          existingBadge.remove();
        }
      });

      closeModal();
    } catch (err) {
      showError(`Network error: ${err.message || err}`);
      submitBtn.disabled = false;
      submitLabel.textContent = 'Regenerate';
    }
  }

  document.addEventListener('click', (event) => {
    const btn = event.target.closest('.edit-section-btn');
    if (btn) {
      openModal({
        planId: btn.dataset.planId,
        sectionId: btn.dataset.sectionId,
        sectionTitle: btn.dataset.sectionTitle,
      });
    }
  });

  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  submitBtn.addEventListener('click', submit);

  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !backdrop.hidden) closeModal();
  });
})();
```

- [ ] **Step 4: Start the server and verify end-to-end UI**

Run: `python app.py`
In the browser, open a plan detail page. Click an Edit button. Expected:
- Modal opens with the section title pre-filled.
- Typing a comment and clicking Regenerate shows "Regenerating…" then closes the modal.
- The iframe content updates to the new plan HTML.
- Stale badges update in the sidebar for downstream sections.

- [ ] **Step 5: Commit**

```bash
git add templates/plan_detail.html static/js/section_edit.js static/css/section_edit.css
git commit -m "feat(ui): section edit modal with regenerate flow and live stale-badge updates"
```

---

## Task 9: Manual end-to-end verification

The unit tests mock the LLM; this step validates the real loop.

- [ ] **Step 1: Start the server**

Run: `python app.py`

- [ ] **Step 2: Pick a plan and edit a section**

Open any existing plan. Click Edit on `food_program`. Type a concrete request (e.g., "Make the tone more conservative and reduce bold claims about being the best in the city."). Leave the image checkbox unchecked. Submit.

Expected:
- Modal closes after a few seconds.
- Preview iframe shows updated food_program content with softer tone.
- Sidebar now shows Stale badges on all menu-related sections (`menu_structure`, `menu_morning`, `menu_core_dayparts`, `menu_signature_items`, `menu_supporting_items`, `equipment_requirements`).

- [ ] **Step 3: Regenerate the image**

Click Edit on `environment_atmosphere`. Enter "Shift toward a brighter, more minimal Scandinavian feel." Check the regenerate-image box. Submit.

Expected:
- Iframe updates with new copy AND a new image that visibly differs from the old one.

- [ ] **Step 4: Verify revision history persists**

In the DB: `sqlite3 instance/concept_lb.sqlite "SELECT id, plan_id, section_id, user_comment, created_at FROM section_revisions ORDER BY id DESC LIMIT 5;"`
Expected: two rows corresponding to the two edits above, with the actual user comments.

- [ ] **Step 5: Verify PDF export reflects latest content**

Trigger the existing PDF export for the plan. Open the PDF.
Expected: the PDF includes the edited section content (not the original pre-edit version), because the PDF pipeline renders from `plan_json`, which has been updated.

- [ ] **Step 6: If all four pass, mark feature done.**

---

## Out of Scope (explicitly)

- **Revision rollback UI.** Revisions are persisted for audit; a "restore previous version" UI is a later task.
- **Per-section diff view.** Users see the new content, not a diff against the old version.
- **Automatic dependent regeneration.** We only flag; the user decides whether to regenerate dependents.
- **Editing intake/concept fields.** Only generated section content is editable here.
- **Retroactive stale-flagging on existing DB rows at migration time.** Stale flags only start accumulating from the next edit forward.
