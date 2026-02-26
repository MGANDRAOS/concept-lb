import json
from typing import Any, Dict

from orchestration.openai_client import call_model_json
from orchestration.repair import repair_json

ASSUMPTIONS_SYSTEM_PROMPT = """
You are Concept LB.

TASK:
Generate a Lebanon-calibrated assumptions table for a restaurant concept in USD.

STRICT OUTPUT:
Return ONLY valid JSON:
{
  "assumptions_table": [
    { "label": "...", "value": "...", "explanation": "..." }
  ],
  "disclaimer": "..."
}

RULES:
- Use ranges when appropriate.
- Do NOT claim you have real market data or citations.
- Be practical and investor-ready.
- Keep disclaimer short and clear.
"""

ASSUMPTIONS_USER_PROMPT_TEMPLATE = """
CONCEPT_OBJECT (JSON):
{concept_json}

Generate assumptions for rent, salaries/labor, utilities, marketing, packaging, equipment ranges, and typical operating ratios.
"""


def generate_assumptions(concept: Dict[str, Any]) -> Dict[str, Any]:
    concept_json = json.dumps(concept, ensure_ascii=False)

    user_prompt = ASSUMPTIONS_USER_PROMPT_TEMPLATE.format(concept_json=concept_json)

    # Attempt 1
    try:
        result = call_model_json(
            system_prompt=ASSUMPTIONS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_name="gpt-5.2",
            reasoning_effort=None,
            max_output_tokens=1400,
        )
    except Exception:
        # Attempt 2: retry with more tokens + tighter wording
        try:
            result = call_model_json(
                system_prompt=ASSUMPTIONS_SYSTEM_PROMPT
                + "\n\nIMPORTANT: Keep explanations short (max 18 words each). Keep JSON compact.",
                user_prompt=user_prompt,
                model_name="gpt-5.2",
                reasoning_effort=None,
                max_output_tokens=1800,
            )
        except Exception:
            # Attempt 3: repair/regenerate
            expected_hint = """
Expected JSON:
{
  "assumptions_table": [
    { "label": "...", "value": "...", "explanation": "..." }
  ],
  "disclaimer": "..."
}
Rules:
- assumptions_table must be a list with at least 8 rows
- disclaimer must be a short string
"""
            result = repair_json(
                broken_output="The previous assumptions output was invalid or truncated. Regenerate valid JSON assumptions.",
                expected_hint=expected_hint,
                model_name="gpt-5.2",
            )

    # Validate shape
    if "assumptions_table" not in result or not isinstance(result["assumptions_table"], list) or len(result["assumptions_table"]) < 5:
        raise ValueError("Assumptions output missing assumptions_table list or too few rows.")
    if "disclaimer" not in result or not isinstance(result["disclaimer"], str) or not result["disclaimer"].strip():
        raise ValueError("Assumptions output missing disclaimer string.")

    return result