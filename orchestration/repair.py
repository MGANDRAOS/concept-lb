from typing import Any, Dict

from orchestration.json_utils import local_json_repair
from orchestration.openai_client import call_model_json


REPAIR_SYSTEM_PROMPT = """
You are a strict JSON repair tool.

TASK:
You will receive invalid or truncated JSON. Repair it into valid JSON that matches the expected structure.

RULES:
- Return ONLY valid JSON. No markdown. No commentary.
- Do not add new content unless required to close structures or complete missing required fields minimally.
- Preserve the user's content as much as possible.
"""


def repair_json(
    *,
    broken_output: str,
    expected_hint: str,
    model_name: str = "gpt-5.2",
) -> Dict[str, Any]:
    # Fast path: deterministic local repair, no API call. Handles the common
    # LLM malformations (unescaped quotes, missing commas, truncation). When
    # this returns a dict, the caller's shape-validation decides if it's usable.
    local = local_json_repair(broken_output)
    if local is not None:
        return local

    user_prompt = f"""
BROKEN_OUTPUT:
{broken_output}

EXPECTED_STRUCTURE_HINT:
{expected_hint}

Return repaired JSON only.
""".strip()

    return call_model_json(
        system_prompt=REPAIR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_name=model_name,
        reasoning_effort=None,
        max_output_tokens=16000,
    )
