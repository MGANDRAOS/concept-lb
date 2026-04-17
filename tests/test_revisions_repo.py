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
