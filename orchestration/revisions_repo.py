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
