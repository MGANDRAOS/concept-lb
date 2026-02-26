import json
from typing import Any, Dict, List

from orchestration.openai_client import call_model_json
from orchestration.repair import repair_json


BUNDLE_SYSTEM_PROMPT = """
You are Concept LB, a restaurant concept development system.

TASK:
Generate MULTIPLE requested sections for a restaurant concept plan in ONE response.

STRICT OUTPUT RULES:
- Return ONLY valid JSON. No markdown. No extra text.
- Output must match ONE of these shapes:

A) Normal bundle:
{
  "sections": [
    {
      "id": "...",
      "title": "...",
      "blocks": [
        { "type": "paragraph", "text": "..." },
        { "type": "bullets", "items": ["...", "..."] },
        { "type": "callout", "title": "...", "text": "..." },
        { "type": "table", "columns": ["..."], "rows": [["..."]] }
      ]
    }
  ]
}

B) Bundle WITH assumptions:
{
  "sections": [ ... ],
  "assumptions_table": [
    { "label": "...", "value": "...", "explanation": "..." }
  ],
  "disclaimer": "..."
}

CONTENT RULES:
- For EACH section:
  - title MUST match the spec title EXACTLY.
  - id MUST match the spec id EXACTLY.
  - Include ALL required block types listed in the spec.
  - Do NOT reference other sections.
  - Do NOT mention AI or prompts.
- Keep content consultant-grade and structured.
""".strip()


BUNDLE_USER_PROMPT_TEMPLATE = """
CONCEPT_OBJECT (JSON):
{concept_json}

SECTION_SPECS_LIST (JSON array):
{specs_json}

INSTRUCTIONS:
- Generate ALL sections in SECTION_SPECS_LIST.
- Output sections in the SAME ORDER as provided.
- Respect max_words per section.
{assumptions_instruction}
""".strip()


def _validate_required_blocks(section_spec: Dict[str, Any], section_dict: Dict[str, Any]) -> None:
    blocks = section_dict.get("blocks", [])
    present_types = {b.get("type") for b in blocks if isinstance(b, dict)}

    for required in section_spec.get("required_blocks", []):
        if required not in present_types:
            raise ValueError(
                f"Section '{section_spec['id']}' missing required block '{required}'. "
                f"Present: {sorted(list(present_types))}"
            )


def generate_sections_bundle(
    concept: Dict[str, Any],
    section_specs: List[Dict[str, Any]],
    *,
    include_assumptions: bool,
    model_name: str = "gpt-5.2",
    max_output_tokens: int = 3200,
) -> Dict[str, Any]:

    concept_json = json.dumps(concept, ensure_ascii=False)
    specs_json = json.dumps(section_specs, ensure_ascii=False)

    assumptions_instruction = ""
    if include_assumptions:
        assumptions_instruction = """
Also include assumptions_table and disclaimer in the SAME JSON response.
Assumptions must cover:
- Rent
- Labor/salaries
- Utilities
- Marketing
- Packaging
- Equipment range
- Typical operating ratios
Use realistic Lebanon-calibrated USD ranges.
Do NOT claim real market citations.
"""

    user_prompt = BUNDLE_USER_PROMPT_TEMPLATE.format(
        concept_json=concept_json,
        specs_json=specs_json,
        assumptions_instruction=assumptions_instruction,
    )

    # Attempt 1
    try:
        result = call_model_json(
            system_prompt=BUNDLE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_name=model_name,
            reasoning_effort=None,
            max_output_tokens=max_output_tokens,
        )
    except Exception:
        # Attempt 2: slightly larger token budget
        result = call_model_json(
            system_prompt=BUNDLE_SYSTEM_PROMPT + "\n\nIMPORTANT: Keep JSON compact.",
            user_prompt=user_prompt,
            model_name=model_name,
            reasoning_effort=None,
            max_output_tokens=max(max_output_tokens, 4000),
        )

    # Repair if shape broken
    if not isinstance(result, dict) or "sections" not in result:
        expected_hint = """
Expected JSON:
{
  "sections": [ { "id":"...","title":"...","blocks":[...] } ],
  "assumptions_table": [ { "label":"...","value":"...","explanation":"..." } ],
  "disclaimer": "..."
}
- sections must be non-empty list
- titles and ids must match specs
"""
        result = repair_json(
            broken_output="Previous output invalid. Regenerate valid JSON bundle.",
            expected_hint=expected_hint,
            model_name=model_name,
        )

    sections = result.get("sections")
    
    expected_ids = [s["id"] for s in section_specs]
    returned_ids = [s.get("id") for s in sections]

    if returned_ids != expected_ids:
        raise ValueError(
            f"Section order mismatch. Expected {expected_ids}, got {returned_ids}"
        )
        
    if not isinstance(sections, list) or len(sections) == 0:
        raise ValueError("Bundle output missing non-empty 'sections'.")

    # Validate each section
    spec_by_id = {s["id"]: s for s in section_specs}

    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Each section must be an object.")

        section_id = section.get("id")
        if section_id not in spec_by_id:
            raise ValueError(f"Unexpected section id: {section_id}")

        spec = spec_by_id[section_id]

        if section.get("title") != spec.get("title"):
            raise ValueError(
                f"Title mismatch for '{section_id}'. "
                f"Expected '{spec.get('title')}', got '{section.get('title')}'."
            )

        _validate_required_blocks(spec, section)

    # Validate assumptions if requested
    if include_assumptions:
        table = result.get("assumptions_table")
        disclaimer = result.get("disclaimer")

        if not isinstance(table, list) or len(table) < 6:
            raise ValueError("Assumptions table missing or too small.")
        if not isinstance(disclaimer, str) or not disclaimer.strip():
            raise ValueError("Disclaimer missing.")
        
    if len(result["sections"]) != len(section_specs):
        raise ValueError(
            f"Model returned {len(result['sections'])} sections but expected {len(section_specs)}."
        )    

    return result