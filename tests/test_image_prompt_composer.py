from unittest.mock import patch

from orchestration.image_prompt_composer import compose_image_prompt


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
