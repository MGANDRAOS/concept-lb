import json
import os
from typing import Any, Dict, Optional

from openai import OpenAI


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in .env and restart the server.")
    return OpenAI(api_key=api_key)


def call_model_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    reasoning_effort: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Uses the OpenAI Responses API.
    Forces JSON-only output.
    """

    client = _get_client()

    strict_system = (
        system_prompt.strip()
        + "\n\nReturn ONLY valid JSON. No markdown. No explanations."
    )

    input_messages = [
        {
            "role": "system",
            "content": strict_system,
        },
        {
            "role": "user",
            "content": user_prompt.strip(),
        },
    ]

    request_kwargs: Dict[str, Any] = {
        "model": model_name,
        "input": input_messages,
    }

    if max_output_tokens is not None:
        request_kwargs["max_output_tokens"] = max_output_tokens

    if reasoning_effort is not None:
        request_kwargs["reasoning"] = {"effort": reasoning_effort}

    response = client.responses.create(**request_kwargs)

    # Extract text output safely
    raw_text = response.output_text
    if not raw_text:
        raise ValueError("Model returned empty response.")

    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Model did not return valid JSON. Raw output:\n{raw_text[:500]}"
        ) from exc