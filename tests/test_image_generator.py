from unittest.mock import MagicMock, patch

from orchestration.image_generator import generate_section_images


def _mock_openai_images_response():
    """Mimic OpenAI DALL-E images.generate(...) response shape."""
    response = MagicMock()
    item = MagicMock()
    item.url = "https://example.invalid/fake-image.png"
    response.data = [item]
    return response


def test_uses_composed_prompt_when_composer_succeeds(fake_concept):
    with patch(
        "orchestration.image_generator.compose_image_prompt",
        return_value="A composed concept-specific prompt.",
    ) as mocked_compose, patch(
        "orchestration.image_generator._get_client"
    ) as mocked_client_getter:
        client = MagicMock()
        client.images.generate.return_value = _mock_openai_images_response()
        mocked_client_getter.return_value = client

        result = generate_section_images(
            concept_name="Fig & Fire",
            concept_description="Neapolitan pizza and natural wine in Beirut.",
            section_id="environment_atmosphere",
            section_title="The Environment & Atmosphere",
            concept=fake_concept,
        )

    assert result is not None
    image_url, alt_text = result
    assert image_url == "https://example.invalid/fake-image.png"
    assert alt_text == "Fig & Fire - The Environment & Atmosphere"

    # Composer was called with the concept
    mocked_compose.assert_called_once()
    assert mocked_compose.call_args.kwargs["concept"] == fake_concept
    assert mocked_compose.call_args.kwargs["section_id"] == "environment_atmosphere"

    # DALL-E was called with the composed prompt (not the generic one)
    client.images.generate.assert_called_once()
    dalle_kwargs = client.images.generate.call_args.kwargs
    assert "A composed concept-specific prompt." in dalle_kwargs["prompt"]


def test_falls_back_to_generic_when_composer_raises(fake_concept):
    with patch(
        "orchestration.image_generator.compose_image_prompt",
        side_effect=RuntimeError("LLM unavailable"),
    ), patch("orchestration.image_generator._get_client") as mocked_client_getter:
        client = MagicMock()
        client.images.generate.return_value = _mock_openai_images_response()
        mocked_client_getter.return_value = client

        result = generate_section_images(
            concept_name="Fig & Fire",
            concept_description="Neapolitan pizza in Beirut.",
            section_id="food_program",
            section_title="The Food Program",
            concept=fake_concept,
        )

    assert result is not None
    dalle_prompt = client.images.generate.call_args.kwargs["prompt"]
    # Generic fallback signature
    assert "Photorealistic photograph of a restaurant scene" in dalle_prompt
    assert "Neapolitan pizza in Beirut." in dalle_prompt


def test_returns_none_for_unmapped_section(fake_concept):
    result = generate_section_images(
        concept_name="Fig & Fire",
        concept_description="Neapolitan pizza in Beirut.",
        section_id="mission",  # not in IMAGE_SECTIONS
        section_title="Mission",
        concept=fake_concept,
    )
    assert result is None


def test_returns_none_when_dalle_fails(fake_concept):
    with patch(
        "orchestration.image_generator.compose_image_prompt",
        return_value="ok",
    ), patch("orchestration.image_generator._get_client") as mocked_client_getter:
        client = MagicMock()
        client.images.generate.side_effect = RuntimeError("API down")
        mocked_client_getter.return_value = client

        result = generate_section_images(
            concept_name="Fig & Fire",
            concept_description="x",
            section_id="food_program",
            section_title="Food",
            concept=fake_concept,
        )

    assert result is None


def test_uses_generic_when_concept_not_provided():
    """Back-compat: callers who don't pass concept still work."""
    with patch("orchestration.image_generator._get_client") as mocked_client_getter:
        client = MagicMock()
        client.images.generate.return_value = _mock_openai_images_response()
        mocked_client_getter.return_value = client

        result = generate_section_images(
            concept_name="Fig & Fire",
            concept_description="Neapolitan pizza in Beirut.",
            section_id="food_program",
            section_title="Food",
        )

    assert result is not None
    dalle_prompt = client.images.generate.call_args.kwargs["prompt"]
    assert "Photorealistic photograph of a restaurant scene" in dalle_prompt
