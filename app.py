from flask import Flask, jsonify, request
from flask_cors import CORS
from config import Config
from datetime import datetime
from orchestration.openai_client import call_model_json
from orchestration.normalization import normalize_intake
from orchestration.section_specs import SECTION_SPECS, should_include_section
from orchestration.section_generator import generate_section
from orchestration.assumptions_generator import generate_assumptions
from schemas.plan_schema import FinalPlan


app = Flask(__name__, static_folder="static", static_url_path="/")
CORS(app)

app.config.from_object(Config)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@app.route("/api/test-openai", methods=["POST"])
def test_openai():
    payload = request.get_json(force=True) or {}
    user_text = payload.get("text", "Say hello as JSON")

    result = call_model_json(
        system_prompt="You are a strict JSON generator.",
        user_prompt=f'Return a JSON object with one key "reply" responding to: {user_text}',
        model_name="gpt-5.2",   # your chosen model
        reasoning=None,
        max_output_tokens=200,
    )
    return jsonify(result)

@app.route("/api/generate", methods=["POST"])
def generate():
    intake = request.get_json(force=True) or {}

    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    # Pass B: generate sections
    sections = []
    for spec in SECTION_SPECS:
        if not should_include_section(spec, concept):
            continue

        section_payload = generate_section(concept, spec)
        sections.append(section_payload["section"])

    # Pass C: assumptions
    assumptions = generate_assumptions(concept)

    # Convert assumptions to a section (Choice B)
    assumptions_section = {
        "id": "assumptions_table_section",
        "title": "Assumptions Table (Lebanon-Calibrated)",
        "blocks": [
            {"type": "paragraph", "text": assumptions["disclaimer"]},
            {
                "type": "table",
                "columns": ["Assumption", "Value", "Explanation"],
                "rows": [[r["label"], r["value"], r["explanation"]] for r in assumptions["assumptions_table"]],
            },
        ],
    }
    sections.append(assumptions_section)

    # Assemble final plan
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
        "assumptions_table": assumptions["assumptions_table"],
        "disclaimer": assumptions["disclaimer"],
    }

    # Validate final plan schema
    validated = FinalPlan.model_validate(final_plan)

    return jsonify(validated.model_dump())

@app.route("/api/generate-preview", methods=["POST"])
def generate_preview():
    intake = request.get_json(force=True) or {}

    normalized = normalize_intake(intake)
    concept = normalized["concept"]

    sections = []

    for spec in SECTION_SPECS:
        if not should_include_section(spec, concept):
            continue

        section_payload = generate_section(concept, spec)
        sections.append(section_payload)

    return jsonify({
        "concept": concept,
        "sections_preview": sections
    })


if __name__ == "__main__":
    app.run(debug=True)