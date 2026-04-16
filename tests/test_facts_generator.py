from unittest.mock import patch

import pytest

from orchestration.facts_generator import generate_facts


def _fake_response(n: int = 3):
    return {
        "facts": [
            {"text": f"Fact {i} about something.", "topic": f"TOPIC-{i}"}
            for i in range(n)
        ]
    }


def test_generate_facts_happy_path(fake_concept):
    with patch(
        "orchestration.facts_generator.call_model_json",
        return_value=_fake_response(25),
    ) as mocked:
        facts = generate_facts(fake_concept, count=25)

    assert len(facts) == 25
    assert all("text" in f and "topic" in f for f in facts)
    # User prompt contains key concept fields
    kwargs = mocked.call_args.kwargs
    assert "Fig & Fire" in kwargs["user_prompt"]
    assert "Beirut" in kwargs["user_prompt"]
    assert kwargs["model_name"] == "gpt-5.4-nano-2026-03-17"


def test_generate_facts_normalizes_topic_to_upper(fake_concept):
    with patch(
        "orchestration.facts_generator.call_model_json",
        return_value={"facts": [{"text": "A fact.", "topic": "local market"}]},
    ):
        facts = generate_facts(fake_concept, count=1)
    assert facts[0]["topic"] == "LOCAL MARKET"


def test_generate_facts_drops_malformed_items(fake_concept):
    with patch(
        "orchestration.facts_generator.call_model_json",
        return_value={
            "facts": [
                {"text": "Good fact.", "topic": "GOOD"},
                {"text": "", "topic": "EMPTY"},
                {"topic": "NO-TEXT"},
                "not a dict",
                {"text": "   ", "topic": "WHITESPACE"},
            ],
        },
    ):
        facts = generate_facts(fake_concept, count=5)
    assert len(facts) == 1
    assert facts[0]["text"] == "Good fact."


def test_generate_facts_raises_on_missing_key(fake_concept):
    with patch(
        "orchestration.facts_generator.call_model_json",
        return_value={"wrong_key": []},
    ):
        with pytest.raises(ValueError, match="malformed"):
            generate_facts(fake_concept, count=5)


def test_generate_facts_raises_on_all_unusable(fake_concept):
    with patch(
        "orchestration.facts_generator.call_model_json",
        return_value={"facts": [{"text": ""}, {"topic": "x"}]},
    ):
        with pytest.raises(ValueError, match="no usable facts"):
            generate_facts(fake_concept, count=5)
