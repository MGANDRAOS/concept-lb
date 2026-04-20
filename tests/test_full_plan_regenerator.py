from unittest.mock import patch

import pytest

from orchestration.full_plan_regenerator import regenerate_full_plan


def _fake_bundle_response():
    return {
        "sections": [
            {"id": "mission", "title": "Mission",
             "blocks": [{"type": "paragraph", "text": "regenerated mission respecting user edit"},
                        {"type": "bullets", "items": ["a", "b"]}]},
        ]
    }


def test_regenerate_full_plan_passes_pending_edits_to_bundle_generator(fake_concept):
    pending = {
        "mission": {
            "blocks": [{"type": "paragraph", "text": "USER-TYPED REPLACEMENT"}],
            "user_comment": "tone should be conservative",
            "updated_at": "2026-04-19T00:00:00Z",
        },
    }
    existing_sections = [
        {"id": "mission", "title": "Mission",
         "blocks": [{"type": "paragraph", "text": "old"},
                    {"type": "bullets", "items": ["old-a", "old-b"]}]},
    ]

    with patch("orchestration.full_plan_regenerator.generate_sections_bundle",
               return_value=_fake_bundle_response()) as mocked:
        new_sections, used_edits = regenerate_full_plan(
            concept=fake_concept,
            existing_sections=existing_sections,
            pending_edits=pending,
            model_name="gpt-5.4-nano-2026-03-17",
        )

    assert len(new_sections) >= 1
    assert new_sections[0]["id"] == "mission"
    assert used_edits == ["mission"]

    # The concept passed into the bundle generator must carry the user feedback.
    _, kwargs = mocked.call_args
    concept_arg = kwargs["concept"]
    assert "USER-TYPED REPLACEMENT" in str(concept_arg)
    assert "tone should be conservative" in str(concept_arg)


def test_regenerate_full_plan_with_no_pending_still_runs(fake_concept):
    existing_sections = [
        {"id": "mission", "title": "Mission",
         "blocks": [{"type": "paragraph", "text": "old"},
                    {"type": "bullets", "items": ["a"]}]},
    ]
    with patch("orchestration.full_plan_regenerator.generate_sections_bundle",
               return_value=_fake_bundle_response()):
        new_sections, used_edits = regenerate_full_plan(
            concept=fake_concept,
            existing_sections=existing_sections,
            pending_edits={},
            model_name="gpt-5.4-nano-2026-03-17",
        )
    assert used_edits == []
    assert len(new_sections) >= 1
