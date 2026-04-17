import json
from typing import Any, Dict, Optional

from orchestration.openai_client import call_model_json
from orchestration.section_bundle_generator import (
    BUNDLE_SYSTEM_PROMPT,
    _validate_required_blocks,
)
from orchestration.section_specs import SECTION_SPECS


_REGEN_USER_TEMPLATE = """
CONCEPT_OBJECT (JSON):
{concept_json}

SECTION_SPEC (single-section mode):
{spec_json}

EXISTING_SECTION (what the reader currently sees; JSON):
{existing_section_json}

USER_EDIT_COMMENT:
\"\"\"{user_comment}\"\"\"

INSTRUCTIONS:
- Regenerate ONLY the single section described in SECTION_SPEC.
- Apply the USER_EDIT_COMMENT as steering: respect the user's requested
  changes in tone, emphasis, length, or content.
- If EXISTING_SECTION is provided, preserve anything the user didn't
  explicitly ask to change.
- Output must match the normal bundle shape with exactly ONE section:

{{
  "sections": [
    {{
      "id": "...",
      "title": "...",
      "blocks": [ ... ]
    }}
  ]
}}

- `id` and `title` MUST match SECTION_SPEC exactly.
- Include ALL required_blocks listed in SECTION_SPEC.
- Do NOT include assumptions_table or disclaimer.
- Do NOT include any other sections.
""".strip()


_REGEN_MODEL = "gpt-5.2"
_REGEN_MAX_TOKENS = 4000


def _find_spec(section_id: str) -> Dict[str, Any]:
    for spec in SECTION_SPECS:
        if spec["id"] == section_id:
            return spec
    raise KeyError(f"Unknown section_id: {section_id!r}")


def regenerate_section(
    *,
    concept: Dict[str, Any],
    section_id: str,
    existing_section: Optional[Dict[str, Any]],
    user_comment: str,
) -> Dict[str, Any]:
    """Regenerate a single section with a steering user comment.

    Raises:
        KeyError: if section_id is not a known section.
        ValueError: if the LLM returns the wrong section or misses required blocks.
    """
    spec = _find_spec(section_id)

    user_prompt = _REGEN_USER_TEMPLATE.format(
        concept_json=json.dumps(concept, ensure_ascii=False),
        spec_json=json.dumps(spec, ensure_ascii=False),
        existing_section_json=(
            json.dumps(existing_section, ensure_ascii=False)
            if existing_section is not None else "null"
        ),
        user_comment=user_comment or "",
    )

    result = call_model_json(
        system_prompt=BUNDLE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_name=_REGEN_MODEL,
        max_output_tokens=_REGEN_MAX_TOKENS,
    )

    sections = result.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError(f"Regenerator response had no sections: {result!r}")

    new_section = sections[0]
    if new_section.get("id") != section_id:
        raise ValueError(
            f"Regenerator did not return section {section_id!r}; got {new_section.get('id')!r}"
        )

    _validate_required_blocks(spec, new_section)
    return new_section
