import json
from typing import Any, Dict, Optional

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


def _local_repair_truncated_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Fast in-process repair for the most common LLM truncation pattern: an unterminated
    string followed by unclosed brackets/braces. Walks the text, tracks string state and
    bracket stack, then closes whatever's still open and tries json.loads. Returns the
    parsed dict on success, or None if the result still isn't a valid JSON object.
    """
    if not text:
        return None

    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return None

    stack = []
    in_string = False
    escape = False

    for c in text:
        if escape:
            escape = False
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "{" or c == "[":
            stack.append(c)
        elif c == "}" or c == "]":
            if stack:
                stack.pop()

    repaired = text
    if in_string:
        repaired += '"'
    for opener in reversed(stack):
        repaired += "}" if opener == "{" else "]"

    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def repair_json(
    *,
    broken_output: str,
    expected_hint: str,
    model_name: str = "gpt-5.2",
) -> Dict[str, Any]:
    # Fast path: close unterminated string + dangling brackets locally. No API call.
    # When this succeeds the caller's shape-validation decides whether the result is
    # usable; if it isn't, the caller raises and the user sees the failure faster.
    local = _local_repair_truncated_json(broken_output)
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
