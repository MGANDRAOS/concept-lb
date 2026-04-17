from unittest.mock import patch

import pytest

from orchestration.section_regenerator import regenerate_section


def _fake_llm_response():
    return {
        "sections": [
            {
                "id": "mission",
                "title": "Mission",
                "blocks": [
                    {"type": "paragraph", "text": "A tighter, more conservative mission."},
                    {"type": "bullets", "items": ["clear", "concise"]},
                ],
            }
        ]
    }


def _existing_section():
    return {
        "id": "mission",
        "title": "Mission",
        "blocks": [
            {"type": "paragraph", "text": "Original verbose mission statement."},
            {"type": "bullets", "items": ["verbose", "rambly"]},
        ],
    }


def test_regenerate_returns_new_section_and_passes_user_comment(fake_concept):
    with patch(
        "orchestration.section_regenerator.call_model_json",
        return_value=_fake_llm_response(),
    ) as mocked:
        new_section = regenerate_section(
            concept=fake_concept,
            section_id="mission",
            existing_section=_existing_section(),
            user_comment="Make it shorter and more conservative.",
        )

    assert new_section["id"] == "mission"
    assert new_section["title"] == "Mission"
    blocks = new_section["blocks"]
    assert blocks[0]["type"] == "paragraph"
    assert "conservative" in blocks[0]["text"]

    # User prompt carries both the user comment and the existing section JSON
    _, kwargs = mocked.call_args
    up = kwargs["user_prompt"]
    assert "Make it shorter and more conservative." in up
    assert "Original verbose mission statement." in up


def test_regenerate_raises_when_llm_returns_wrong_section_id(fake_concept):
    bad_response = {
        "sections": [
            {"id": "vision", "title": "Vision", "blocks": [{"type": "paragraph", "text": "x"}]}
        ]
    }
    with patch(
        "orchestration.section_regenerator.call_model_json",
        return_value=bad_response,
    ):
        with pytest.raises(ValueError, match="did not return section 'mission'"):
            regenerate_section(
                concept=fake_concept,
                section_id="mission",
                existing_section=_existing_section(),
                user_comment="x",
            )


def test_regenerate_raises_when_required_blocks_missing(fake_concept):
    bad_response = {
        "sections": [
            {"id": "mission", "title": "Mission", "blocks": [{"type": "paragraph", "text": "only paragraph"}]}
        ]
    }
    with patch(
        "orchestration.section_regenerator.call_model_json",
        return_value=bad_response,
    ):
        with pytest.raises(ValueError, match="missing required block"):
            regenerate_section(
                concept=fake_concept,
                section_id="mission",
                existing_section=_existing_section(),
                user_comment="x",
            )


def test_regenerate_raises_for_unknown_section_id(fake_concept):
    with pytest.raises(KeyError):
        regenerate_section(
            concept=fake_concept,
            section_id="not_a_real_section",
            existing_section=None,
            user_comment="x",
        )
