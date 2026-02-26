from datetime import datetime

from flask import Flask,  request, render_template
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
def preview_page():
    return render_template("index.html")





if __name__ == "__main__":
    app.run(debug=True)