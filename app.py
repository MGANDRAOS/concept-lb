# app.py
import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template, request, Response
from flask_cors import CORS
from pydantic import BaseModel

from config import Config
from orchestration.financials_engine import compute_derived_financials
from orchestration.normalization import normalize_intake
from orchestration.section_specs import SECTION_SPECS, should_include_section
from orchestration.section_bundle_generator import generate_sections_bundle
from schemas.plan_schema import FinalPlan

from concurrent.futures import ThreadPoolExecutor, as_completed

from orchestration.db import init_db, connect
from orchestration.plans_repo import create_plan, list_plans, get_plan
from schemas.plan_store_schema import PlanRecordCreate, utc_now_iso

from playwright.sync_api import sync_playwright



app = Flask(__name__, static_folder="static", static_url_path="/", instance_relative_config=True)
CORS(app)
app.config.from_object(Config)

# --- DB init (instance/ folder method) ---
DB_PATH = init_db(app.instance_path)

def db_conn():
    return connect(DB_PATH)


# --- Jobs memory store (existing) ---
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _chunk_list(items, chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


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

    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))

    chunk_size = int(request.args.get("chunk_size", 6))
    chunks = list(_chunk_list(included_specs, chunk_size))
    total_chunks = max(1, len(chunks))

    max_workers = int(request.args.get("max_workers", 3))

    def _run_bundle(chunk_index: int, specs_chunk: list, include_assumptions: bool):
        bundle = generate_sections_bundle(
            concept=concept,
            section_specs=specs_chunk,
            include_assumptions=include_assumptions,
            model_name="gpt-5.2",
            max_output_tokens=3200 if not include_assumptions else 4200,
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
    return redirect("/wizard")


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
        model="gpt-5.2",
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


def _run_generation_job(job_id: str, intake: dict, chunk_size: int, max_workers: int):
    with app.app_context():
        try:
            _job_update(job_id, percent=2, message="Normalizing intake…", log="Normalizing intake…")
            normalized = normalize_intake(intake)
            concept = normalized["concept"]
            concept["derived_financials"] = compute_derived_financials(concept)
            normalized["concept"] = concept

            included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
            included_specs.sort(key=lambda s: s.get("order", 0))

            chunks = list(_chunk_list(included_specs, chunk_size))
            total_chunks = max(1, len(chunks))
            _job_update(job_id, percent=6, message=f"Preparing {total_chunks} bundles…", log=f"Preparing {total_chunks} bundles…")

            def _run_bundle(chunk_index: int, specs_chunk: list, include_assumptions: bool):
                _job_update(job_id, message=f"Generating sections bundle {chunk_index+1}/{total_chunks}…", log=f"Bundle {chunk_index+1}/{total_chunks} started")
                bundle = generate_sections_bundle(
                    concept=concept,
                    section_specs=specs_chunk,
                    include_assumptions=include_assumptions,
                    model_name="gpt-5.2",
                    max_output_tokens=3200 if not include_assumptions else 4200,
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
            }

            validated = FinalPlan.model_validate(final_plan).model_dump()

            # Render HTML snapshot and persist the plan
            plan_html = render_template("plan_view.html", plan=validated)
            plan_id = _persist_plan_record(
                job_id=job_id,
                intake=intake,
                normalized=normalized,
                plan=validated,
                plan_html=plan_html,
                status="complete",
            )

            with JOBS_LOCK:
                JOBS[job_id]["status"] = "done"
                JOBS[job_id]["plan"] = validated
                JOBS[job_id]["plan_id"] = plan_id

            _job_update(job_id, percent=100, message="Done ✅", log="Done ✅")

        except Exception as e:
            err = str(e)
            # Persist failure record too (intake + normalized if available)
            try:
                _persist_plan_record(
                    job_id=job_id,
                    intake=intake,
                    normalized=None,
                    plan=None,
                    plan_html=None,
                    status="failed",
                    error_message=err,
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
    print("=== /api/generate-job payload ===")
    print(json.dumps(intake, ensure_ascii=False, indent=2)[:5000])
    print("=== payload keys ===", list(intake.keys()))
    chunk_size = int(request.args.get("chunk_size", 6))
    max_workers = int(request.args.get("max_workers", 3))

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
        }

    t = threading.Thread(
        target=_run_generation_job,
        args=(job_id, intake, chunk_size, max_workers),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/jobs/<job_id>", methods=["GET"])
def job_page(job_id: str):
    return render_template("job_status.html", job_id=job_id)


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
                yield f"event: progress\ndata: {json.dumps(payload)}\n\n"

                if job["status"] == "done":
                    done_payload = {"view_url": f"/jobs/{job_id}/view", "plan_id": job.get("plan_id")}
                    yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                    return

                if job["status"] == "error":
                    err_payload = {"error": job.get("error") or "Unknown error"}
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


@app.route("/plans/<plan_id>", methods=["GET"])
def plan_detail_route(plan_id: str):
    conn = db_conn()
    try:
        plan = get_plan(conn, plan_id)
    finally:
        conn.close()

    if not plan:
        return "Plan not found", 404

    if _wants_json():
        return jsonify(plan.model_dump())

    return render_template("plan_detail.html", plan=plan.model_dump())


@app.route("/plans/<plan_id>/export/pdf", methods=["GET"])
def plan_export_pdf(plan_id: str):
    conn = db_conn()
    try:
        plan = get_plan(conn, plan_id)
    finally:
        conn.close()

    if not plan:
        return "Plan not found", 404

    html = plan.plan_html
    if not html:
        return "No cached HTML for this plan. Regenerate or store HTML snapshot.", 400

    # Render HTML in headless Chromium and print to PDF
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Use base URL so relative assets can resolve if you ever add them
        page.set_content(html, wait_until="load")

        page.add_style_tag(content="""
        @page {
        size: A4;
        margin: 0;
        }
        html, body {
        margin: 0;
        padding: 0;
        }
        """)
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
        )

        browser.close()

    filename = f"ConceptLB_{(plan.title or plan.id).replace(' ', '_')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
    )


if __name__ == "__main__":
    app.run(debug=True)