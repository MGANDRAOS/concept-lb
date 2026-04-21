import json
import os
import threading
from typing import Any, Dict, Optional

from openai import OpenAI


# ── Token usage tracker (thread-safe accumulator) ──────────────
class TokenTracker:
    """Accumulates token usage across multiple API calls."""
    def __init__(self):
        self._lock = threading.Lock()
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, input_tokens: int, output_tokens: int):
        with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.calls += 1

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    def summary(self) -> Dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "api_calls": self.calls,
        }

    def cost(self, model_name: str) -> Dict[str, Any]:
        """Calculate cost based on model pricing."""
        pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["default"])
        input_cost = self.input_tokens * pricing["input"] / 1_000_000
        output_cost = self.output_tokens * pricing["output"] / 1_000_000
        return {
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
            "total_cost_usd": round(input_cost + output_cost, 4),
            "model": model_name,
        }


# Pricing per 1M tokens
MODEL_PRICING = {
    "gpt-5.4-2026-03-05":       {"input": 2.50, "output": 10.00},
    "gpt-5.4-nano-2026-03-17":  {"input": 0.20, "output": 1.25},
    "gpt-5.2":                   {"input": 1.75, "output": 14.00},
    "default":                   {"input": 1.75, "output": 14.00},
}

# Global tracker for current generation job (reset per job)
_current_tracker: Optional[TokenTracker] = None


def start_tracking() -> TokenTracker:
    """Start a new token tracker for a generation job."""
    global _current_tracker
    _current_tracker = TokenTracker()
    return _current_tracker


def get_tracker() -> Optional[TokenTracker]:
    return _current_tracker


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
    Tracks token usage automatically.
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

    # Track token usage
    usage = getattr(response, "usage", None)
    if usage and _current_tracker:
        _current_tracker.add(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
        )

    # Extract text output safely
    raw_text = response.output_text
    if not raw_text:
        raise ValueError("Model returned empty response.")

    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        err = ValueError(
            f"Model did not return valid JSON. Raw output:\n{raw_text[:500]}"
        )
        # Attach the full raw text so callers can attempt repair without re-calling the model.
        err.raw_text = raw_text
        raise err from exc