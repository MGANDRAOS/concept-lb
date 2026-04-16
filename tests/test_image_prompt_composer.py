from unittest.mock import patch

from orchestration.image_prompt_composer import _concept_brief, compose_image_prompt


SECTION_FRAMING = {
    "environment_atmosphere": (
        "wide-angle interior photograph of a dining room with warm moody lighting"
    ),
    "food_program": (
        "close-up overhead food photography of plated dishes on a dark slate table"
    ),
}


def test_compose_returns_llm_text_when_call_succeeds(fake_concept):
    fake_response = {
        "prompt": (
            "Photorealistic wide-angle interior shot of a rustic Neapolitan pizza "
            "restaurant in Beirut with exposed brick walls, candlelight, and an "
            "open kitchen with a wood-fired oven visible."
        )
    }
    with patch(
        "orchestration.image_prompt_composer.call_model_json",
        return_value=fake_response,
    ) as mocked:
        result = compose_image_prompt(
            concept=fake_concept,
            section_id="environment_atmosphere",
            section_title="The Environment & Atmosphere",
            framing=SECTION_FRAMING["environment_atmosphere"],
        )

    assert result == fake_response["prompt"]
    # Sanity: the user prompt we built mentioned concept + framing
    _, kwargs = mocked.call_args
    assert "Fig & Fire" in kwargs["user_prompt"]
    assert "Neapolitan pizza" in kwargs["user_prompt"]
    assert "exposed brick" in kwargs["user_prompt"]
    assert SECTION_FRAMING["environment_atmosphere"] in kwargs["user_prompt"]
    assert kwargs["model_name"] == "gpt-5.4-nano-2026-03-17"


import pytest


def test_compose_raises_on_missing_prompt_field(fake_concept):
    with patch(
        "orchestration.image_prompt_composer.call_model_json",
        return_value={"wrong_key": "oops"},
    ):
        with pytest.raises(ValueError, match="malformed"):
            compose_image_prompt(
                concept=fake_concept,
                section_id="food_program",
                section_title="The Food Program",
                framing=SECTION_FRAMING["food_program"],
            )


def test_compose_raises_on_empty_prompt(fake_concept):
    with patch(
        "orchestration.image_prompt_composer.call_model_json",
        return_value={"prompt": "   "},
    ):
        with pytest.raises(ValueError, match="malformed"):
            compose_image_prompt(
                concept=fake_concept,
                section_id="food_program",
                section_title="The Food Program",
                framing=SECTION_FRAMING["food_program"],
            )


def test_concept_brief_handles_alcohol_flag_true():
    brief = _concept_brief({"alcohol_flag": True})
    assert "Alcohol: yes" in brief


def test_concept_brief_handles_alcohol_flag_false_and_missing():
    brief_false = _concept_brief({"alcohol_flag": False})
    brief_missing = _concept_brief({})
    assert "Alcohol: no" in brief_false
    assert "Alcohol: no" in brief_missing


def test_concept_brief_joins_list_field_with_comma_space():
    brief = _concept_brief({
        "target_audience": ["students", "tourists", "locals"],
    })
    assert "Target audience: students, tourists, locals" in brief


def test_concept_brief_renders_unspecified_for_missing_list():
    brief = _concept_brief({})
    assert "Target audience: unspecified" in brief


def test_concept_brief_handles_explicit_none_scalar():
    """Key present but value None — the fix for the flagged bug."""
    brief = _concept_brief({
        "concept_name": None,
        "cuisine_type": None,
        "neighborhood_type": None,
        "service_model": None,
        "price_positioning": None,
        "beverage_direction": None,
    })
    # None should not leak into the brief as the literal string "None"
    assert "None" not in brief
    assert "Concept name: unnamed" in brief
    assert "Cuisine: unspecified" in brief
    assert "Neighborhood type: unspecified" in brief
    assert "Service model: unspecified" in brief
    assert "Price positioning: unspecified" in brief
    assert "Beverage direction: unspecified" in brief
