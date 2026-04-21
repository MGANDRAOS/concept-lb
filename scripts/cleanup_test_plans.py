"""One-off cleanup: remove unnamed test plans whose intake_json contains
'Pierre' or 'Fat Monk'. Keeps plans with a non-empty title.

Run locally:
    python scripts/cleanup_test_plans.py

Run on Railway (after `railway link`):
    railway run python scripts/cleanup_test_plans.py
"""
import json
import os
import sqlite3
import sys


# Paths to check — local dev vs Railway-mounted volume
CANDIDATE_PATHS = [
    os.path.join("instance", "concept_lb.sqlite"),
    "/app/instance/concept_lb.sqlite",
]


def find_db() -> str:
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    print("ERROR: concept_lb.sqlite not found in expected locations:", CANDIDATE_PATHS)
    sys.exit(1)


def main() -> None:
    db_path = find_db()
    print(f"DB: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    rows = conn.execute(
        "SELECT id, title, intake_json FROM plans"
    ).fetchall()

    candidates = []
    for r in rows:
        intake = r["intake_json"] or ""
        has_leak = ("Pierre" in intake) or ("Fat Monk" in intake)
        has_title = bool((r["title"] or "").strip())
        if has_leak and not has_title:
            candidates.append(r["id"])

    print(f"Found {len(candidates)} unnamed plans with Pierre/Fat Monk in intake:")
    for cid in candidates:
        print(f"  - {cid}")

    if not candidates:
        print("Nothing to delete.")
        return

    # Foreign keys cascade from section_revisions → plans, so deleting the
    # plan row also cleans up its revisions.
    conn.executemany(
        "DELETE FROM plans WHERE id = ?",
        [(cid,) for cid in candidates],
    )
    conn.commit()
    print(f"Deleted {len(candidates)} plans.")

    conn.close()


if __name__ == "__main__":
    main()
