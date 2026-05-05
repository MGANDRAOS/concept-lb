import json
from typing import Any, Dict, Optional

import json_repair

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


def _local_repair(text: str) -> Optional[Dict[str, Any]]:
    """
    Fast in-process repair using the json-repair library, which handles the common
    LLM JSON malformations: unescaped quotes inside strings, missing commas, smart
    quotes, trailing commas, and truncation (unterminated strings + unclosed brackets).
    Returns the parsed dict on success, or None if the input doesn't look like a JSON
    object or repair didn't yield one.
    """
    if not text:
        return None
    if not text.lstrip().startswith("{"):
        return None
    try:
        parsed = json_repair.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) and parsed else None


def repair_json(
    *,
    broken_output: str,
    expected_hint: str,
    model_name: str = "gpt-5.2",
) -> Dict[str, Any]:
    # Fast path: deterministic local repair, no API call. Handles the common
    # LLM malformations (unescaped quotes, missing commas, truncation). When
    # this returns a dict, the caller's shape-validation decides if it's usable.
    local = _local_repair(broken_output)
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
