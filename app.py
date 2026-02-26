from datetime import datetime

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from config import Config
from orchestration.openai_client import call_model_json
from orchestration.normalization import normalize_intake
from orchestration.section_specs import SECTION_SPECS, should_include_section
from orchestration.section_bundle_generator import generate_sections_bundle
from schemas.plan_schema import FinalPlan


app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app)
app.config.from_object(Config)


def _chunk_list(items, chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


@app.route("/api/generate", methods=["POST"])
def generate():
    intake = request.get_json(force=True) or {}

    # Pass A: normalize
    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    # Build included specs list (conditionals applied)
    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))

    # Pass B + C merged: bundle sections into fewer calls
    # Tune chunk_size to control #calls vs risk. 6 is a safe default.
    chunk_size = int(request.args.get("chunk_size", 6))

    sections = []
    assumptions_table = None
    disclaimer = None

    chunks = list(_chunk_list(included_specs, chunk_size))
    for idx, specs_chunk in enumerate(chunks):
        is_last_chunk = idx == (len(chunks) - 1)

        bundle = generate_sections_bundle(
            concept,
            specs_chunk,
            include_assumptions=is_last_chunk,
            model_name="gpt-5.2",
            max_output_tokens=3200 if not is_last_chunk else 4200,
        )

        # Extend sections
        sections.extend(bundle["sections"])

        # Capture assumptions from last chunk
        if is_last_chunk:
            assumptions_table = bundle.get("assumptions_table")
            disclaimer = bundle.get("disclaimer")

    if not assumptions_table or not disclaimer:
        raise ValueError("Assumptions were not generated in the last bundle as expected.")

    # Convert assumptions to a final section (so it renders like others)
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

    # Pass D: assemble + validate
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
    return jsonify(validated.model_dump())


@app.route("/api/render-html", methods=["POST"])
def render_html():
    """
    Input: FinalPlan JSON
    Output: HTML via Jinja templates
    """
    payload = request.get_json(force=True) or {}
    validated = FinalPlan.model_validate(payload)
    plan_dict = validated.model_dump()
    return render_template("plan_view.html", plan=plan_dict)


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
    for idx, specs_chunk in enumerate(chunks):
        is_last_chunk = idx == (len(chunks) - 1)

        bundle = generate_sections_bundle(
            concept,
            specs_chunk,
            include_assumptions=is_last_chunk,
            model_name="gpt-5.2",
            max_output_tokens=3200 if not is_last_chunk else 4200,
        )

        sections.extend(bundle["sections"])
        if is_last_chunk:
            assumptions_table = bundle.get("assumptions_table")
            disclaimer = bundle.get("disclaimer")

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


@app.route("/preview", methods=["GET"])
def preview_page():
    return render_template("index.html")















## Not Used Endpoints (but keep for testing and future features):

@app.route("/api/generate-preview", methods=["POST"])
def generate_preview():
    intake = request.get_json(force=True) or {}
    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    # Keep preview cheap: first chunk only, no assumptions
    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))
    preview_specs = included_specs[:2]

    bundle = generate_sections_bundle(
        concept,
        preview_specs,
        include_assumptions=False,
        model_name="gpt-5.2",
        max_output_tokens=1800,
    )

    return jsonify({"concept": concept, "sections_preview": bundle["sections"]})


@app.route("/api/preview-html", methods=["POST"])
def preview_html():
    """
    Cheap HTML preview using bundled generation (minimized calls).
    - Generates first N sections using chunked bundle calls
    - Returns HTML so you can judge formatting/quality fast
    """
    intake = request.get_json(force=True) or {}

    # Pass A: normalize
    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    # Included specs
    included_specs = [s for s in SECTION_SPECS if should_include_section(s, concept)]
    included_specs.sort(key=lambda s: s.get("order", 0))

    # Controls (URL params)
    chunk_size = int(request.args.get("chunk_size", 6))          # how many sections per OpenAI call
    preview_chunks = int(request.args.get("preview_chunks", 1))  # how many bundle calls to run (1 = cheapest)

    # Take only the sections covered by preview_chunks * chunk_size
    max_sections = preview_chunks * chunk_size
    preview_specs = included_specs[:max_sections]

    # Bundle in minimized calls
    spec_chunks = list(_chunk_list(preview_specs, chunk_size))

    sections = []
    for specs_chunk in spec_chunks:
        bundle = generate_sections_bundle(
            concept=concept,
            section_specs=specs_chunk,
            include_assumptions=False,   # preview: no assumptions to save tokens
            model_name="gpt-5.2",
            max_output_tokens=3200,
        )
        sections.extend(bundle["sections"])

    # Build a lightweight plan dict just for rendering
    plan_dict = {
        "plan_meta": {
            "concept_name": concept.get("concept_name", "Concept Preview"),
            "country": concept.get("country", ""),
            "currency": "USD",
            "language": concept.get("language", "en"),
            "blueprint_version": "preview",
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        "sections": sections,
        "assumptions_table": [],
        "disclaimer": "",
    }

    return render_template("plan_view.html", plan=plan_dict)


if __name__ == "__main__":
    app.run(debug=True)