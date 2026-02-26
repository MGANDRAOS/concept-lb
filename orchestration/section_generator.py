import json
from typing import Any, Dict

from orchestration.openai_client import call_model_json
from orchestration.repair import repair_json


SECTION_SYSTEM_PROMPT = """
You are Concept LB, a restaurant concept development system.

TASK:
Generate ONLY the requested section for a restaurant concept plan.

STRICT OUTPUT RULES:
- Return ONLY valid JSON. No markdown. No extra text.
- Output must match:
{
  "section": {
    "id": "...",
    "title": "...",
    "blocks": [
      { "type": "paragraph", "text": "..." },
      { "type": "bullets", "items": ["...", "..."] },
      { "type": "callout", "title": "...", "text": "..." },
      { "type": "table", "columns": ["..."], "rows": [["..."]]}
    ]
  }
}

CONTENT RULES:
- Title must match the section spec title exactly.
- Use creative founder energy, but keep it consultant-grade and structured.
- Do not reference other sections.
- Do not mention AI, prompts, or the model.
"""


SECTION_USER_PROMPT_TEMPLATE = """
CONCEPT_OBJECT (JSON):
{concept_json}

SECTION_SPEC (JSON):
{spec_json}

Generate the section now.
"""


def _validate_required_blocks(section_spec: Dict[str, Any], section_dict: Dict[str, Any]) -> None:
    section = section_dict.get("section", {})
    blocks = section.get("blocks", [])
    present_types = {b.get("type") for b in blocks if isinstance(b, dict)}

    for required in section_spec.get("required_blocks", []):
        if required not in present_types:
            raise ValueError(
                f"Section '{section_spec['id']}' missing required block type '{required}'. "
                f"Present types: {sorted(list(present_types))}"
            )


def generate_section(concept: Dict[str, Any], section_spec: Dict[str, Any]) -> Dict[str, Any]:
    concept_json = json.dumps(concept, ensure_ascii=False)
    spec_json = json.dumps(section_spec, ensure_ascii=False)

    user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(concept_json=concept_json, spec_json=spec_json)

    # Allow per-section token override
    max_tokens = section_spec.get("max_output_tokens", 900)

    # Attempt 1: normal generation
    try:
        section_dict = call_model_json(
            system_prompt=SECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_name="gpt-5.2",
            reasoning_effort=None,
            max_output_tokens=max_tokens,
        )
        _validate_required_blocks(section_spec, section_dict)
        return section_dict
    except Exception as first_error:
        # Attempt 2: retry with higher token budget
        try:
            section_dict = call_model_json(
                system_prompt=SECTION_SYSTEM_PROMPT + "\n\nIMPORTANT: Keep JSON compact. Avoid long sentences.",
                user_prompt=user_prompt,
                model_name="gpt-5.2",
                reasoning_effort=None,
                max_output_tokens=max(1400, max_tokens),
            )
            _validate_required_blocks(section_spec, section_dict)
            return section_dict
        except Exception:
            # Attempt 3: Repair pass (best-effort)
            # We use the raw output if we can. But call_model_json raises before returning raw.
            # So we repair by asking the model to regenerate minimally using the spec as hint.
            expected_hint = f"""
                Expected JSON keys:
                - section.id must be "{section_spec['id']}"
                - section.title must be "{section_spec['title']}"
                - section.blocks must include types: {section_spec.get('required_blocks', [])}
                """
            broken = (
                "The previous output was invalid JSON or truncated. "
                "Regenerate ONLY valid JSON for this section based on the concept and section spec."
            )

            repaired = repair_json(
                broken_output=broken,
                expected_hint=expected_hint,
                model_name="gpt-5.2",
            )
            _validate_required_blocks(section_spec, repaired)
            return repaired