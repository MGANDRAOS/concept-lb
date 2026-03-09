import base64
import os
from typing import Optional

from openai import OpenAI


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in .env and restart the server.")
    return OpenAI(api_key=api_key)


def generate_concept_image(
    *,
    concept_name: str,
    concept_description: str,
    section_title: str,
    style: str = "modern restaurant interior design",
) -> tuple[str, str]:
    """
    Generate an image for a section using DALL-E 3.
    
    Returns:
        Tuple of (image_url, alt_text)
    """
    client = _get_client()

    prompt = f"""Create a professional restaurant concept image for:
    
Restaurant Name: {concept_name}
Concept: {concept_description}
Section Focus: {section_title}
Style: {style}

Generate a cohesive, professional visual representation suitable for a restaurant concept document.
Focus on clarity, modern design principles, and restaurant-appropriate aesthetics."""

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    alt_text = f"{concept_name} - {section_title}"

    return image_url, alt_text


def generate_section_images(
    *,
    concept_name: str,
    concept_description: str,
    section_id: str,
    section_title: str,
) -> Optional[tuple[str, str]]:
    """
    Generate an image for specific sections that benefit from visual representation.
    Returns None if the section shouldn't have an image.
    
    Returns:
        Tuple of (image_url, alt_text) or None
    """
    
    # Map section IDs to image generation styles
    IMAGE_SECTIONS = {
        "environment_atmosphere": "upscale restaurant ambiance, interior design, lighting mood, seating arrangement",
        "food_program": "restaurant kitchen, food plating, cuisine presentation, culinary excellence",
        "menu_structure": "modern menu design, cuisine presentation, ingredient showcase, food photography",
        "service_staffing_model": "professional restaurant service team, staff training, service excellence, hospitality",
        "location_strategy": "restaurant location, storefront design, neighborhood presence, accessibility",
        "concept_overview": "restaurant concept branding, visual identity, dining experience, ambiance",
    }

    if section_id not in IMAGE_SECTIONS:
        return None

    style = IMAGE_SECTIONS[section_id]

    try:
        image_url, alt_text = generate_concept_image(
            concept_name=concept_name,
            concept_description=concept_description,
            section_title=section_title,
            style=style,
        )
        return image_url, alt_text
    except Exception as e:
        # Gracefully handle image generation failures
        print(f"Warning: Failed to generate image for section {section_id}: {str(e)}")
        return None
