# app.py
import base64
import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict
import urllib.request

from flask import Flask, jsonify, redirect, render_template, request, Response
from flask_cors import CORS
from pydantic import BaseModel

from config import Config
from orchestration.financials_engine import compute_derived_financials
from orchestration.normalization import normalize_intake
from orchestration.section_specs import SECTION_SPECS, should_include_section
from orchestration.section_bundle_generator import generate_sections_bundle
from orchestration.facts_generator import generate_facts
from schemas.plan_schema import FinalPlan
from orchestration.risk_engine import evaluate_risk

from concurrent.futures import ThreadPoolExecutor, as_completed

from orchestration.db import init_db, connect
from orchestration.plans_repo import create_plan, list_plans, get_plan, delete_plan, apply_section_update
from orchestration.section_regenerator import regenerate_section
from orchestration.section_dependencies import downstream_of
from orchestration.revisions_repo import insert_revision, revisions_for_section
from orchestration.image_generator import generate_section_images
from orchestration.pending_edits_repo import (
    get_pending_edits,
    set_pending_edit,
    clear_pending_edit,
    clear_all_pending,
)
from orchestration.full_plan_regenerator import regenerate_full_plan
from schemas.plan_store_schema import PlanRecordCreate, utc_now_iso

from playwright.sync_api import sync_playwright



_HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_HERE, "templates"),
    static_folder=os.path.join(_HERE, "static"),
    static_url_path="/",
    instance_relative_config=True,
)
CORS(app)
app.config.from_object(Config)

# --- DB init (instance/ folder method) ---
DB_PATH = init_db(app.instance_path)

def db_conn():
    return connect(DB_PATH)


class _DotDict(dict):
    """Wrap a dict for Jinja2 — supports both dot-notation and dict access (.get, [key])."""
    def __init__(self, d):
        super().__init__(d or {})
        for k, v in (d or {}).items():
            if isinstance(v, dict):
                self[k] = _DotDict(v)
            elif isinstance(v, list):
                self[k] = [_DotDict(i) if isinstance(i, dict) else i for i in v]

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None


# --- Jobs memory store (existing) ---
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _chunk_list(items, chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    _BEIRUT_TZ = ZoneInfo("Asia/Beirut")
except Exception:
    _BEIRUT_TZ = None


@app.template_filter("pretty_datetime")
def _pretty_datetime_filter(value: Any) -> str:
    """Render an ISO-8601 timestamp in Beirut time as 'Apr 17, 2026 · 04:38'.

    Stored timestamps are UTC. Naive datetimes are assumed UTC. If
    zoneinfo is unavailable (pre-3.9 without backports), a fixed UTC+3
    offset is used as a best-effort fallback (correct in summer, one
    hour off during EET winter — Beirut is currently on EEST).
    """
    if not value:
        return ""
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except Exception:
        return str(value)

    from datetime import timezone, timedelta
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if _BEIRUT_TZ is not None:
        dt = dt.astimezone(_BEIRUT_TZ)
    else:
        dt = dt.astimezone(timezone(timedelta(hours=3)))
    return dt.strftime("%b %d, %Y · %H:%M")


def _cell_to_str(v: Any) -> str:
    """Coerce a table-cell-like value to a string for schema validation.

    The LLM frequently returns numeric values in table rows and
    assumptions table entries. Pydantic rejects non-strings. Drop trailing
    .0 on whole floats to keep table output readable (1000.0 -> "1000").
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _stringify_table_cells(sections: list) -> None:
    """In-place: coerce every table-block row cell to str across all sections."""
    for section in sections or []:
        for block in section.get("blocks", []) or []:
            if block.get("type") == "table":
                coerced_rows = []
                for row in block.get("rows") or []:
                    if isinstance(row, list):
                        coerced_rows.append([_cell_to_str(c) for c in row])
                    else:
                        coerced_rows.append([_cell_to_str(row)])
                block["rows"] = coerced_rows
                cols = block.get("columns")
                if isinstance(cols, list):
                    block["columns"] = [_cell_to_str(c) for c in cols]


def _stringify_assumptions_values(assumptions: list) -> list:
    """Return a copy of assumptions_table with numeric `value` fields stringified."""
    out = []
    for r in assumptions or []:
        if not isinstance(r, dict):
            continue
        out.append({
            "label": _cell_to_str(r.get("label", "")),
            "value": _cell_to_str(r.get("value", "")),
            "explanation": _cell_to_str(r.get("explanation", "")),
        })
    return out


def _convert_images_to_data_uris(sections: list) -> list:
    """
    Convert external image URLs in sections to base64 data URIs.
    This prevents network timeouts during PDF generation.
    """
    for section in sections:
        blocks = section.get("blocks", [])
        for block in blocks:
            if block.get("type") == "image" and block.get("url", "").startswith("http"):
                try:
                    url = block["url"]
                    with urllib.request.urlopen(url, timeout=15) as response:
                        image_data = response.read()
                        content_type = response.headers.get("Content-Type", "image/png")
                        base64_data = base64.b64encode(image_data).decode("utf-8")
                        data_uri = f"data:{content_type};base64,{base64_data}"
                        block["url"] = data_uri
                except Exception as e:
                    print(f"Warning: Failed to convert image URL to data URI: {url}. Error: {e}")
                    # Keep original URL as fallback
    return sections


@app.route("/api/generate-html", methods=["POST"])
def generate_html():
    """
    Convenience endpoint:
    - Runs generation (same logic)
    - Returns HTML directly
    """
    intake = request.get_json(force=True) or {}
    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    concept["derived_financials"] = compute_derived_financials(concept)
    



    concept["risk_report"] = evaluate_risk(
        concept,
        concept["derived_financials"],
    ).model_dump()

    normalized["concept"] = concept

    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))

    chunk_size = int(request.args.get("chunk_size", 4))
    chunks = list(_chunk_list(included_specs, chunk_size))
    total_chunks = max(1, len(chunks))

    max_workers = int(request.args.get("max_workers", 3))

    def _run_bundle(chunk_index: int, specs_chunk: list, include_assumptions: bool):
        bundle = generate_sections_bundle(
            concept=concept,
            section_specs=specs_chunk,
            include_assumptions=include_assumptions,
            model_name="gpt-5.2",
            max_output_tokens=8000 if not include_assumptions else 10000,
            generate_images=True,
        )
        return chunk_index, bundle

    results_by_idx = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, specs_chunk in enumerate(chunks):
            include_assumptions = (idx == len(chunks) - 1)
            futures.append(executor.submit(_run_bundle, idx, specs_chunk, include_assumptions))
        for fut in as_completed(futures):
            idx, bundle = fut.result()
            results_by_idx[idx] = bundle

    # Assemble in order
    sections = []
    assumptions_table = None
    disclaimer = None

    for idx in range(len(chunks)):
        bundle = results_by_idx[idx]
        sections.extend(bundle["sections"])
        if idx == len(chunks) - 1:
            assumptions_table = bundle.get("assumptions_table")
            disclaimer = bundle.get("disclaimer")

    if not assumptions_table or not disclaimer:
        raise ValueError("Assumptions missing from last bundle response.")

    assumptions_table = _stringify_assumptions_values(assumptions_table)

    assumptions_section = {
        "id": "assumptions_table_section",
        "title": "Assumptions Table (Lebanon-Calibrated)",
        "blocks": [
            {"type": "paragraph", "text": disclaimer},
            {
                "type": "table",
                "columns": ["Assumption", "Value", "Explanation"],
                "rows": [[r["label"], r["value"], r["explanation"]] for r in assumptions_table],
            },
        ],
    }
    sections.append(assumptions_section)

    # Convert external image URLs to data URIs for faster/offline rendering
    sections = _convert_images_to_data_uris(sections)
    # Coerce any numeric/non-string cells the LLM slipped into table blocks.
    _stringify_table_cells(sections)

    final_plan = {
        "plan_meta": {
            "concept_name": concept["concept_name"],
            "country": concept["country"],
            "currency": "USD",
            "language": concept["language"],
            "blueprint_version": "1.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        "sections": sections,
        "assumptions_table": assumptions_table,
        "disclaimer": disclaimer,
    }

    validated = FinalPlan.model_validate(final_plan)
    return render_template("plan_view.html", plan=validated.model_dump())


@app.route("/", methods=["GET"])
def home():
    return render_template("landing.html")


@app.route("/wizard", methods=["GET"])
def wizard():
    return render_template("wizard.html")


# --- SSE helpers (existing) ---
def _job_update(job_id: str, *, percent: float = None, message: str = None, log: str = None):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        if percent is not None:
            job["percent"] = float(percent)
        if message is not None:
            job["message"] = str(message)
        if log:
            job["logs"].append(str(log))


def _persist_plan_record(
    *,
    job_id: str,
    intake: Dict[str, Any],
    normalized: Dict[str, Any] | None,
    plan: Dict[str, Any] | None,
    plan_html: str | None,
    status: str,
    error_message: str | None = None,
    model_name: str | None = None,
):
    now = utc_now_iso()
    plan_id = uuid.uuid4().hex

    title = None
    locale = None
    if plan and isinstance(plan, dict):
        meta = (plan.get("plan_meta") or {})
        title = meta.get("concept_name") or None
        locale = meta.get("language") or None

    record = PlanRecordCreate(
        id=plan_id,
        created_at=now,
        updated_at=now,
        status=status,  # "complete" or "failed"
        title=title,
        mode="phase1",
        locale=locale,
        model=model_name or "unknown",
        job_id=job_id,
        intake=intake or {},
        normalized_intake=normalized,
        plan=plan,
        plan_html=plan_html,
        error_message=error_message,
    )

    conn = db_conn()
    try:
        create_plan(conn, record)
    finally:
        conn.close()

    return plan_id


class _JobCancelled(Exception):
    """Raised at cooperative cancel points when the user requested abort."""
    pass


def _check_cancel(job_id: str) -> None:
    """Raise _JobCancelled if the user asked to cancel this job."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job and job.get("cancel_requested"):
            raise _JobCancelled()


def _run_generation_job(job_id: str, intake: dict, chunk_size: int, max_workers: int, model_name: str = "gpt-5.2"):
    with app.app_context():
        try:
            from orchestration.openai_client import start_tracking
            tracker = start_tracking()

            _job_update(job_id, percent=2, message="Normalizing intake…", log="Normalizing intake…")
            normalized = normalize_intake(intake)
            concept = normalized["concept"]

            _check_cancel(job_id)

            # Stash concept_name early so the job_status page can show it.
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["concept_name"] = concept.get("concept_name") or ""

            # Kick off facts generation on a background thread. Failure must NOT
            # break plan generation — degrade to no facts silently.
            def _facts_worker(jid: str, concept_snapshot: Dict[str, Any]):
                try:
                    result = generate_facts(concept_snapshot)
                    with JOBS_LOCK:
                        if jid in JOBS:
                            JOBS[jid]["facts"] = result
                except Exception as fexc:
                    print(f"Warning: facts generation failed: {fexc}")

            threading.Thread(
                target=_facts_worker,
                args=(job_id, dict(concept)),
                daemon=True,
            ).start()

            concept["derived_financials"] = compute_derived_financials(concept)

            concept["risk_report"] = evaluate_risk(
                concept,
                concept["derived_financials"],
            ).model_dump()

            normalized["concept"] = concept

            included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
            included_specs.sort(key=lambda s: s.get("order", 0))

            chunks = list(_chunk_list(included_specs, chunk_size))
            total_chunks = max(1, len(chunks))
            _job_update(job_id, percent=6, message=f"Preparing {total_chunks} bundles…", log=f"Preparing {total_chunks} bundles…")

            _check_cancel(job_id)

            def _run_bundle(chunk_index: int, specs_chunk: list, include_assumptions: bool):
                _check_cancel(job_id)
                _job_update(job_id, message=f"Generating sections bundle {chunk_index+1}/{total_chunks}…", log=f"Bundle {chunk_index+1}/{total_chunks} started")
                bundle = generate_sections_bundle(
                    concept=concept,
                    section_specs=specs_chunk,
                    include_assumptions=include_assumptions,
                    model_name=model_name,
                    max_output_tokens=8000 if not include_assumptions else 10000,
                )
                return chunk_index, bundle

            results_by_idx = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for idx, specs_chunk in enumerate(chunks):
                    include_assumptions = (idx == len(chunks) - 1)
                    futures.append(executor.submit(_run_bundle, idx, specs_chunk, include_assumptions))

                completed = 0
                for fut in as_completed(futures):
                    idx, bundle = fut.result()
                    results_by_idx[idx] = bundle
                    completed += 1

                    pct = 10 + (completed / total_chunks) * 80
                    _job_update(job_id, percent=pct, message=f"Bundle {completed}/{total_chunks} done ✅", log=f"Bundle {idx+1}/{total_chunks} done ✅")
                    _check_cancel(job_id)

            # Assemble in correct order
            sections = []
            assumptions_table = None
            disclaimer = None

            for idx in range(len(chunks)):
                bundle = results_by_idx[idx]
                sections.extend(bundle["sections"])
                if idx == len(chunks) - 1:
                    assumptions_table = bundle.get("assumptions_table")
                    disclaimer = bundle.get("disclaimer")

            if not assumptions_table or not disclaimer:
                raise ValueError("Assumptions missing from last bundle response.")

            _job_update(job_id, percent=94, message="Assembling final plan…", log="Assembling final plan…")

            assumptions_table = _stringify_assumptions_values(assumptions_table)

            assumptions_section = {
                "id": "assumptions_table_section",
                "title": "Assumptions Table (Lebanon-Calibrated)",
                "blocks": [
                    {"type": "paragraph", "text": disclaimer},
                    {
                        "type": "table",
                        "columns": ["Assumption", "Value", "Explanation"],
                        "rows": [[r["label"], r["value"], r["explanation"]] for r in assumptions_table],
                    },
                ],
            }
            sections.append(assumptions_section)

            # Convert external image URLs to data URIs for faster/offline rendering
            sections = _convert_images_to_data_uris(sections)
            # Coerce any numeric/non-string cells the LLM slipped into table blocks.
            _stringify_table_cells(sections)

            final_plan = {
                "plan_meta": {
                    "concept_name": concept.get("concept_name", ""),
                    "country": concept.get("country", ""),
                    "currency": "USD",
                    "language": concept.get("language", "en"),
                    "blueprint_version": "1.0",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                },
                "sections": sections,
                "assumptions_table": assumptions_table,
                "disclaimer": disclaimer,
                "risk_report": concept.get("risk_report"),
                "derived_financials": concept.get("derived_financials"),
                "token_usage": {**tracker.summary(), **tracker.cost(model_name)},
            }

            try:
                validated = FinalPlan.model_validate(final_plan).model_dump()
            except Exception as val_err:
                # Log detailed validation error for debugging
                import traceback
                print(f"FinalPlan validation failed: {val_err}")
                print(f"Sections count: {len(sections)}")
                for i, sec in enumerate(sections):
                    block_types = [b.get('type', '?') for b in sec.get('blocks', [])]
                    print(f"  Section {i}: id={sec.get('id')}, blocks={block_types}")
                traceback.print_exc()
                raise

            # Render HTML snapshot and persist the plan
            plan_html = render_template("plan_view.html", plan=validated)
            plan_id = _persist_plan_record(
                job_id=job_id,
                intake=intake,
                normalized=normalized,
                plan=validated,
                plan_html=plan_html,
                status="complete",
                model_name=model_name,
            )

            # Capture token usage
            usage_summary = tracker.summary()
            cost_summary = tracker.cost(model_name)
            token_info = {**usage_summary, **cost_summary}

            with JOBS_LOCK:
                JOBS[job_id]["status"] = "done"
                JOBS[job_id]["plan"] = validated
                JOBS[job_id]["plan_id"] = plan_id
                JOBS[job_id]["token_usage"] = token_info

            _job_update(job_id, percent=100, message="Done ✅", log="Done ✅")

        except _JobCancelled:
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["status"] = "cancelled"
            _job_update(job_id, message="Cancelled", log="Cancelled by user")
            return

        except Exception as e:
            import traceback, io
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            full_tb = buf.getvalue()
            err = f"{type(e).__name__}: {e}\n\nTRACEBACK:\n{full_tb}"

            # If the user asked to cancel, honour that intent: don't leave a
            # "failed" record in the DB. Treat it as a clean cancellation.
            with JOBS_LOCK:
                was_cancelled = bool((JOBS.get(job_id) or {}).get("cancel_requested"))
            if was_cancelled:
                with JOBS_LOCK:
                    if job_id in JOBS:
                        JOBS[job_id]["status"] = "cancelled"
                _job_update(job_id, message="Cancelled", log="Cancelled by user")
                return

            # Persist failure record (intake + normalized if available)
            try:
                _persist_plan_record(
                    job_id=job_id,
                    intake=intake,
                    normalized=None,
                    plan=None,
                    plan_html=None,
                    status="failed",
                    error_message=err,
                    model_name=model_name,
                )
            except Exception:
                # don't crash the job handler because DB write failed
                pass

            with JOBS_LOCK:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = err

            _job_update(job_id, message="Failed ❌", log=f"ERROR: {err}")


@app.route("/api/generate-job", methods=["POST"])
def generate_job():
    intake = request.get_json(force=True) or {}

    chunk_size = int(request.args.get("chunk_size", 4))
    max_workers = int(request.args.get("max_workers", 3))

    # Model selection: allow override via query param or payload
    ALLOWED_MODELS = {"gpt-5.4-2026-03-05", "gpt-5.4-nano-2026-03-17"}
    model_name = request.args.get("model") or intake.pop("_model", None) or "gpt-5.4-nano-2026-03-17"
    if model_name not in ALLOWED_MODELS:
        model_name = "gpt-5.4-nano-2026-03-17"

    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "running",
            "percent": 0.0,
            "message": "Starting…",
            "logs": [],
            "plan": None,
            "error": None,
            "plan_id": None,
            "model": model_name,
            "concept_name": "",
            "facts": None,
            "facts_sent": False,
            "cancel_requested": False,
            "cancelled_sent": False,
        }

    t = threading.Thread(
        target=_run_generation_job,
        args=(job_id, intake, chunk_size, max_workers, model_name),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def job_cancel(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "job not found"}), 404
        if job["status"] in ("done", "error", "cancelled"):
            return jsonify({"ok": True, "status": job["status"]}), 200
        job["cancel_requested"] = True
    return jsonify({"ok": True, "status": "cancelling"}), 200


@app.route("/jobs/<job_id>", methods=["GET"])
def job_page(job_id: str):
    concept_name = ""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job:
            concept_name = job.get("concept_name") or ""
    return render_template("job_status.html", job_id=job_id, concept_name=concept_name)


@app.route("/jobs/<job_id>/view", methods=["GET"])
def job_view(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return "Job not found", 404
        if job["status"] == "error":
            return f"Job failed: {job.get('error','Unknown error')}", 500
        if job["status"] != "done" or not job.get("plan"):
            return "Job still running", 202

        # If persisted, redirect to /plans/<id> so this becomes your canonical view
        plan_id = job.get("plan_id")
        if plan_id:
            return redirect(f"/plans/{plan_id}")

        return render_template("plan_view.html", plan=job["plan"])


@app.route("/api/jobs/<job_id>/events", methods=["GET"])
def job_events(job_id: str):
    def stream():
        last_log_index = 0

        while True:
            facts_event_payload = None
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if not job:
                    yield 'event: job_error\ndata: {"error":"Job not found"}\n\n'
                    return

                logs = job["logs"]
                new_logs = logs[last_log_index:]
                last_log_index = len(logs)

                payload = {
                    "percent": job["percent"],
                    "message": job["message"],
                    "log": ("\n".join(new_logs) if new_logs else None),
                }

                # One-shot facts emission when facts first become available.
                facts = job.get("facts")
                if facts and not job.get("facts_sent"):
                    facts_event_payload = {"facts": facts}
                    job["facts_sent"] = True

                status = job["status"]
                done_payload = None
                err_payload = None
                cancelled_payload = None
                if status == "done":
                    done_payload = {
                        "view_url": f"/jobs/{job_id}/view",
                        "plan_id": job.get("plan_id"),
                        "token_usage": job.get("token_usage"),
                    }
                elif status == "error":
                    err_payload = {"error": job.get("error") or "Unknown error"}
                elif status == "cancelled" and not job.get("cancelled_sent"):
                    cancelled_payload = {"message": "Generation cancelled."}
                    job["cancelled_sent"] = True

            yield f"event: progress\ndata: {json.dumps(payload)}\n\n"

            if facts_event_payload is not None:
                yield f"event: facts\ndata: {json.dumps(facts_event_payload)}\n\n"

            if cancelled_payload is not None:
                yield f"event: cancelled\ndata: {json.dumps(cancelled_payload)}\n\n"
                return

            if done_payload is not None:
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                return

            if err_payload is not None:
                yield f"event: job_error\ndata: {json.dumps(err_payload)}\n\n"
                return

            time.sleep(0.5)

    return Response(stream(), mimetype="text/event-stream")


# --- Plans routes (HTML default, JSON if Accept header requests it) ---
def _wants_json() -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept.lower()


@app.route("/plans", methods=["GET"])
def plans_list_route():
    q = request.args.get("q")
    status = request.args.get("status") or None
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    conn = db_conn()
    try:
        plans = list_plans(conn, q=q, status=status, limit=limit, offset=offset)
    finally:
        conn.close()

    if _wants_json():
        return jsonify([p.model_dump() for p in plans])

    return render_template("plans_list.html", plans=[p.model_dump() for p in plans], q=q, status=status)


@app.route("/api/plans/<plan_id>", methods=["DELETE"])
def plan_delete_route(plan_id: str):
    conn = db_conn()
    try:
        deleted = delete_plan(conn, plan_id)
    finally:
        conn.close()
    if not deleted:
        return jsonify({"ok": False, "error": "plan not found"}), 404
    return jsonify({"ok": True})


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

        # Regenerate the section content; reuse the plan's original model
        try:
            new_section = regenerate_section(
                concept=concept_obj,
                section_id=section_id,
                existing_section=existing_section,
                user_comment=user_comment,
                model_name=plan_view.model,
            )
        except KeyError:
            return jsonify({"ok": False, "error": f"unknown section: {section_id}"}), 400
        except ValueError as ve:
            return jsonify({"ok": False, "error": str(ve)}), 502
        except Exception as e:
            # Surface OpenAI errors (rate limits, quota, context limits, auth) and
            # any other upstream failure as structured JSON so the UI can display them.
            err_type = type(e).__name__
            msg = str(e) or err_type
            # Try to extract a cleaner message from OpenAI-style errors
            try:
                body = getattr(e, "response", None)
                if body is not None and hasattr(body, "json"):
                    data = body.json()
                    api_err = (data or {}).get("error") or {}
                    api_msg = api_err.get("message")
                    if api_msg:
                        msg = api_msg
            except Exception:
                pass
            status_code = 429 if "RateLimit" in err_type or "insufficient_quota" in msg else 502
            return jsonify({
                "ok": False,
                "error": f"{err_type}: {msg}",
                "error_type": err_type,
            }), status_code

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
                image_block = {
                    "type": "image",
                    "url": new_image_url,
                    "alt_text": new_image_alt,
                    "caption": f"Visual representation: {new_section.get('title', '')}",
                }
                blocks = list(new_section.get("blocks") or [])
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
        if not any(s.get("id") == section_id for s in existing_sections):
            plan_data_updated["sections"] = list(existing_sections) + [new_section]

        # Re-render HTML from updated plan_json
        new_plan_html = render_template("plan_view.html", plan=plan_data_updated)

        # If this is the first edit for this section, snapshot the pre-edit
        # content as revision 0 so Revert can restore it.
        prior_revs = revisions_for_section(conn, plan_id=plan_id, section_id=section_id)
        if not prior_revs and existing_section is not None:
            existing_image_block = next(
                (b for b in (existing_section.get("blocks") or []) if b.get("type") == "image"),
                None,
            )
            insert_revision(
                conn,
                plan_id=plan_id,
                section_id=section_id,
                section_title=existing_section.get("title", section_id),
                user_comment="(original — pre-edit snapshot)",
                blocks=existing_section.get("blocks") or [],
                image_url=(existing_image_block or {}).get("url"),
                image_alt=(existing_image_block or {}).get("alt_text"),
            )

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

        # At this point there are always ≥ 2 revisions for this section
        # (the pre-edit snapshot + the one we just inserted), so revert is available.
        return jsonify({
            "ok": True,
            "section": new_section,
            "plan_html": new_plan_html,
            "stale_section_ids": sorted(new_stale),
            "can_revert": True,
        })
    finally:
        conn.close()


@app.route("/api/plans/<plan_id>/sections/<section_id>/revert", methods=["POST"])
def api_revert_section(plan_id: str, section_id: str):
    """Undo the most recent regeneration of `section_id` for `plan_id`.

    Restores the previous revision's blocks + image, rewrites plan_json and
    plan_html, and deletes the most recent revision row so the next revert
    targets the version before it. 400 if no prior revision exists.
    """
    conn = db_conn()
    try:
        plan_view = get_plan(conn, plan_id)
        if plan_view is None:
            return jsonify({"ok": False, "error": "plan not found"}), 404

        revs = revisions_for_section(conn, plan_id=plan_id, section_id=section_id)
        if len(revs) < 2:
            return jsonify({"ok": False, "error": "No earlier version to revert to."}), 400

        current_rev, target_rev = revs[0], revs[1]

        # Reassemble the section from the target revision's stored blocks.
        reverted_blocks = list(target_rev.blocks)
        if target_rev.image_url:
            # Ensure the image block is present at the start; strip any other image first.
            reverted_blocks = [b for b in reverted_blocks if b.get("type") != "image"]
            reverted_blocks.insert(0, {
                "type": "image",
                "url": target_rev.image_url,
                "alt_text": target_rev.image_alt or "",
                "caption": f"Visual representation: {target_rev.section_title}",
            })

        reverted_section = {
            "id": section_id,
            "title": target_rev.section_title,
            "blocks": reverted_blocks,
        }

        # Rebuild plan JSON and HTML.
        plan_data = plan_view.plan or {}
        existing_sections = plan_data.get("sections") or []
        plan_data_updated = dict(plan_data)
        plan_data_updated["sections"] = [
            reverted_section if s.get("id") == section_id else s
            for s in existing_sections
        ]
        new_plan_html = render_template("plan_view.html", plan=plan_data_updated)

        # Preserve the stale set as-is — revert does not recompute stale flags.
        apply_section_update(
            conn,
            plan_id=plan_id,
            new_section=reverted_section,
            new_plan_html=new_plan_html,
            stale_section_ids=plan_view.stale_section_ids or [],
        )

        # Pop the "current" revision so revert stacks naturally.
        conn.execute(
            "DELETE FROM section_revisions WHERE id = ?",
            (current_rev.id,),
        )
        conn.commit()

        remaining = revisions_for_section(conn, plan_id=plan_id, section_id=section_id)

        return jsonify({
            "ok": True,
            "section": reverted_section,
            "plan_html": new_plan_html,
            "stale_section_ids": sorted(plan_view.stale_section_ids or []),
            "can_revert": len(remaining) >= 2,
            "reverted_to_comment": target_rev.user_comment,
        })
    finally:
        conn.close()


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

        # Preserve existing image blocks so images aren't re-generated
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

        # Re-attach preserved images (insert at position 0)
        for sec in new_sections:
            img = existing_images.get(sec.get("id"))
            if img:
                blocks = [b for b in (sec.get("blocks") or [])
                          if b.get("type") != "image"]
                blocks.insert(0, img)
                sec["blocks"] = blocks

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

        # Revisions: one per section
        for sec in new_sections:
            sid = sec.get("id")
            if sid in applied_edit_ids:
                comment = "(full plan regen — edited: " + ", ".join(applied_edit_ids) + ")"
            else:
                comment = "(full plan regen)"
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


@app.route("/plans/<plan_id>", methods=["GET"])
def plan_detail_route(plan_id: str):
    conn = db_conn()
    try:
        plan = get_plan(conn, plan_id)
        if not plan:
            return "Plan not found", 404
        if _wants_json():
            return jsonify(plan.model_dump())

        # Sections with ≥ 2 revisions can be reverted one step.
        sections_with_history = set()
        rows = conn.execute(
            """
            SELECT section_id
            FROM section_revisions
            WHERE plan_id = ?
            GROUP BY section_id
            HAVING COUNT(*) >= 2
            """,
            (plan_id,),
        ).fetchall()
        sections_with_history = {r["section_id"] for r in rows}
        pending_section_ids = set((plan.pending_edits or {}).keys())
    finally:
        conn.close()

    sections_summary = []
    for sec in (plan.plan or {}).get("sections") or []:
        sections_summary.append({
            "id": sec.get("id"),
            "title": sec.get("title"),
        })

    return render_template(
        "plan_detail.html",
        plan=plan.model_dump(),
        sections=sections_summary,
        stale_section_ids=plan.stale_section_ids or [],
        sections_with_history=sections_with_history,
        pending_section_ids=pending_section_ids,
    )


@app.route("/plans/<plan_id>/export/pdf", methods=["GET"])
def plan_export_pdf(plan_id: str):
    conn = db_conn()
    try:
        plan = get_plan(conn, plan_id)
    finally:
        conn.close()

    if not plan:
        return "Plan not found", 404

    plan_data = plan.plan
    if not plan_data:
        return "Plan data not available for PDF export", 400

    # Wrap for Jinja2 dot-notation access
    wrapped = _DotDict(plan_data)

    html = render_template("plan_pdf.html", plan=wrapped)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded", timeout=60000)

        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template='<div style="width:100%;text-align:center;font-size:9px;color:#999;"><span class="pageNumber"></span></div>',
            margin={
                "top": "25mm",
                "bottom": "28mm",
                "left": "22mm",
                "right": "22mm",
            },
        )
        browser.close()

    concept_name = (plan_data.get("plan_meta", {}).get("concept_name", "") or "").strip()
    safe_name = "".join(c for c in concept_name if c.isalnum() or c in " _-").strip() or "plan"
    filename = f"ConceptLB_{safe_name}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/plans/<plan_id>/export/financial-pdf", methods=["GET"])
def plan_export_financial_pdf(plan_id: str):
    conn = db_conn()
    try:
        plan = get_plan(conn, plan_id)
    finally:
        conn.close()

    if not plan:
        return "Plan not found", 404

    plan_data = plan.plan
    if not plan_data:
        return "Plan data not available", 400

    # Get normalized concept data
    concept = plan.normalized_intake
    if not concept:
        return "Normalized intake not available for financial model", 400

    # Generate financial model
    from orchestration.financial_model_generator import generate_financial_model
    fm = generate_financial_model(concept, plan_data.get("derived_financials"))

    concept_name = (plan_data.get("plan_meta", {}) or {}).get("concept_name", "Restaurant")
    date_str = ((plan_data.get("plan_meta", {}) or {}).get("created_at", "") or "")[:10]

    # Wrap dicts for Jinja2 dot-notation access
    fm_wrapped = _DotDict(fm)

    html = render_template(
        "financial_pdf.html",
        fm=fm_wrapped,
        concept_name=concept_name,
        date=date_str,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded", timeout=60000)

        pdf_bytes = page.pdf(
            format="A4",
            landscape=True,
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template='<div style="width:100%;text-align:center;font-size:9px;color:#999;"><span class="pageNumber"></span></div>',
            margin={"top": "18mm", "bottom": "22mm", "left": "15mm", "right": "15mm"},
        )
        browser.close()

    safe_name = "".join(c for c in (concept_name or "plan") if c.isalnum() or c in " _-").strip() or "plan"
    filename = f"ConceptLB_{safe_name}_FinancialModel.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import sys
    os.chdir(_HERE)  # Ensure CWD is project root
    app.run(debug=True, use_reloader="--no-reload" not in sys.argv)