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
