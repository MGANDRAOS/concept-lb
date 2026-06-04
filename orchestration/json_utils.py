"""Low-level JSON recovery helpers shared across the orchestration layer.

This module imports nothing else from `orchestration`, so both
`openai_client` (which self-heals malformed model output) and `repair`
(the last-resort repair pipeline) can use it without a circular import.
"""
import json
from typing import Any, Dict, Optional

import json_repair


def looks_truncated(text: str) -> bool:
    """True when output was almost certainly cut off at the token cap.

    A complete JSON object/array ends with a closing brace/bracket (ignoring
    trailing whitespace). If the model stopped mid-content, the text ends mid
    token instead. Truncation must be recovered by escalating (retrying with
    more tokens), NOT by local repair: json-repair would close the brackets
    around the partial content and silently ship an incomplete result.
    """
    stripped = (text or "").rstrip()
    return not stripped.endswith(("}", "]"))


def local_json_repair(text: str) -> Optional[Dict[str, Any]]:
    """Deterministic in-process repair via the json-repair library.

    Handles the common LLM JSON malformations: unescaped quotes inside strings
    (e.g. an inch-mark like 14"), missing commas, smart quotes, and trailing
    commas (and, for last-resort callers, unterminated strings / unclosed
    brackets). Returns the parsed dict on success, or None when the input is
    not a JSON object or repair did not yield a non-empty dict.
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
