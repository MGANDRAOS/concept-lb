"""call_model_json self-heals complete-but-malformed JSON, but still raises on
truncation so callers can escalate (retry with more tokens). See repair.py and
section_bundle_generator.py for the escalation pattern this protects."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from orchestration import openai_client
from orchestration.openai_client import call_model_json


def _response(text, *, status="completed", reason=None):
    details = SimpleNamespace(reason=reason) if reason is not None else None
    return SimpleNamespace(
        output_text=text,
        status=status,
        incomplete_details=details,
        usage=SimpleNamespace(input_tokens=5, output_tokens=7),
    )


def _patched_client(response):
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: response))
    return patch.object(openai_client, "_get_client", return_value=client)


def _call():
    return call_model_json(system_prompt="s", user_prompt="u", model_name="gpt-5.2")


def test_complete_but_malformed_json_is_locally_repaired():
    # Model wrote an unescaped inch-mark (14") mid-string but finished the
    # structure: output is complete, just syntactically broken. This is the
    # exact failure class behind the production "Something went wrong" crash.
    bad = '{"sections":[{"id":"x","title":"T","blocks":[{"type":"paragraph","text":"a 14" pie"}]}]}'
    with _patched_client(_response(bad)):
        result = _call()
    assert isinstance(result, dict)
    assert result["sections"][0]["id"] == "x"


def test_truncated_json_raises_with_raw_text_for_escalation():
    # Token cap hit: content is genuinely incomplete. Must raise (not silently
    # repair) so bundle/regen/assumptions callers escalate with more tokens.
    cut = '{"sections":[{"id":"x","title":"T","blocks":[{"type":"paragraph","text":"unfinished senten'
    with _patched_client(_response(cut, status="incomplete", reason="max_output_tokens")):
        with pytest.raises(ValueError) as excinfo:
            _call()
    assert getattr(excinfo.value, "raw_text", None) == cut


def test_truncation_detected_by_heuristic_without_api_flag():
    # Even when the API does not flag incompleteness, output ending mid-content
    # (no closing brace) is treated as truncation.
    cut = '{"sections":[{"id":"x","title":"T","blocks":[{"type":"paragraph","text":"unfinished senten'
    with _patched_client(_response(cut, status="completed", reason=None)):
        with pytest.raises(ValueError):
            _call()


def test_valid_json_passes_through():
    good = '{"sections":[{"id":"x","title":"T","blocks":[]}]}'
    with _patched_client(_response(good)):
        result = _call()
    assert result["sections"][0]["title"] == "T"
