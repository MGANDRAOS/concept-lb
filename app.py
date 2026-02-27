import uuid
import time
import json
import threading
from datetime import datetime
from flask import Flask,  request, render_template, jsonify, redirect   
from flask_cors import CORS
from config import Config
from orchestration.normalization import normalize_intake
from orchestration.section_specs import SECTION_SPECS, should_include_section
from orchestration.section_bundle_generator import generate_sections_bundle
from schemas.plan_schema import FinalPlan
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app)
app.config.from_object(Config)

JOBS = {}        # job_id -> dict(status, percent, message, logs, plan, error)
JOBS_LOCK = threading.Lock()

def _chunk_list(items, chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


@app.route("/api/generate-html", methods=["POST"])
def generate_html():
    """
    Convenience endpoint:
    - Runs /api/generate internally (same logic)
    - Returns HTML directly (so you test in browser instantly)
    """
    intake = request.get_json(force=True) or {}

    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))

    chunk_size = int(request.args.get("chunk_size", 6))
    sections = []
    assumptions_table = None
    disclaimer = None

    chunks = list(_chunk_list(included_specs, chunk_size))
    max_workers = int(request.args.get("max_workers", 3))  # start with 3

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


#Progress SSE Helpers
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
            
            
def _run_generation_job(job_id: str, intake: dict, chunk_size: int, max_workers: int):
    try:
        _job_update(job_id, percent=2, message="Normalizing intake…", log="Normalizing intake…")
        normalized = normalize_intake(intake)
        concept = normalized["concept"]

        included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
        included_specs.sort(key=lambda s: s.get("order", 0))

        chunks = list(_chunk_list(included_specs, chunk_size))
        total_chunks = max(1, len(chunks))

        _job_update(job_id, percent=6, message=f"Preparing {total_chunks} bundles…", log=f"Preparing {total_chunks} bundles…")

        def _run_bundle(chunk_index: int, specs_chunk: list, include_assumptions: bool):
            _job_update(job_id, message=f"Generating sections bundle {chunk_index+1}/{total_chunks}…",
                        log=f"Bundle {chunk_index+1}/{total_chunks} started")
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

                # progress 10% -> 90% across chunk completion
                pct = 10 + (completed / total_chunks) * 80
                _job_update(job_id, percent=pct, message=f"Bundle {completed}/{total_chunks} done ✅",
                            log=f"Bundle {idx+1}/{total_chunks} done ✅")

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

        with JOBS_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["plan"] = validated

        _job_update(job_id, percent=100, message="Done ✅", log="Done ✅")

    except Exception as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
        _job_update(job_id, message="Failed ❌", log=f"ERROR: {e}")            


@app.route("/api/generate-job", methods=["POST"])
def generate_job():
    intake = request.get_json(force=True) or {}
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
        }

    t = threading.Thread(
        target=_run_generation_job,
        args=(job_id, intake, chunk_size, max_workers),
        daemon=True
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

            # send progress snapshot
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
                done_payload = {"view_url": f"/jobs/{job_id}/view"}
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                return

            if job["status"] == "error":
                err_payload = {"error": job.get("error") or "Unknown error"}
                yield f"event: job_error\ndata: {json.dumps(err_payload)}\n\n"
                return

            time.sleep(0.5)

    return app.response_class(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)