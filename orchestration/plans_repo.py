# orchestration/plans_repo.py
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from schemas.plan_store_schema import PlanRecordCreate, PlanListItem, PlanView

def _json_dumps_safe(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)

def _json_loads_safe(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        # If corrupted, return None but keep DB record accessible
        return None

def create_plan(conn: sqlite3.Connection, record: PlanRecordCreate) -> str:
    conn.execute(
        """
        INSERT INTO plans (
          id, created_at, updated_at, status, title, mode, locale, model, job_id,
          intake_json, normalized_intake_json, plan_json, plan_html,
          tokens_in, tokens_out, latency_ms, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.created_at,
            record.updated_at,
            record.status,
            record.title,
            record.mode,
            record.locale,
            record.model,
            record.job_id,
            _json_dumps_safe(record.intake) or "{}",
            _json_dumps_safe(record.normalized_intake),
            _json_dumps_safe(record.plan),
            record.plan_html,
            record.tokens_in,
            record.tokens_out,
            record.latency_ms,
            record.error_message,
        ),
    )
    conn.commit()
    return record.id

def list_plans(
    conn: sqlite3.Connection,
    *,
    q: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[PlanListItem]:
    where = []
    params: List[Any] = []

    if status:
        where.append("status = ?")
        params.append(status)

    if q:
        # Simple search in title + id
        where.append("(title LIKE ? OR id LIKE ?)")
        params.append(f"%{q}%")
        params.append(f"%{q}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"""
        SELECT id, created_at, status, title, locale, mode, model
        FROM plans
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    ).fetchall()

    return [
        PlanListItem(
            id=r["id"],
            created_at=r["created_at"],
            status=r["status"],
            title=r["title"],
            locale=r["locale"],
            mode=r["mode"],
            model=r["model"],
        )
        for r in rows
    ]

def delete_plan(conn: sqlite3.Connection, plan_id: str) -> bool:
    """Hard-delete a plan row by id. Returns True if a row was removed."""
    cur = conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    conn.commit()
    return cur.rowcount > 0


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

    pending_raw = r["pending_edits_json"] if "pending_edits_json" in r.keys() else None
    pending_edits: dict = {}
    if pending_raw:
        try:
            p = json.loads(pending_raw)
            if isinstance(p, dict):
                pending_edits = p
        except Exception:
            pending_edits = {}

    deleted_raw = r["deleted_section_ids_json"] if "deleted_section_ids_json" in r.keys() else None
    deleted_ids: list = []
    if deleted_raw:
        try:
            d = json.loads(deleted_raw)
            if isinstance(d, list):
                deleted_ids = [str(x) for x in d]
        except Exception:
            deleted_ids = []

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
        pending_edits=pending_edits,
        deleted_section_ids=deleted_ids,
    )


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