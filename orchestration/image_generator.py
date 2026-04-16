from __future__ import annotations

import os
from typing import Any, Dict, Optional

from openai import OpenAI

from orchestration.image_prompt_composer import compose_image_prompt


IMAGE_SECTIONS = {
    "environment_atmosphere": (
        "wide-angle interior photograph of the dining room, warm moody lighting, "
        "shallow depth of field, natural window light mixed with ambient fill"
    ),
    "food_program": (
        "close-up overhead food photography of plated dishes on a textured table, "
        "shallow depth of field, studio accent lighting, editorial food magazine style"
    ),
    "menu_structure": (
        "lifestyle flat-lay of dishes and fresh ingredients on a tabletop, "
        "colorful garnishes, natural side lighting, editorial food-magazine composition"
    ),
    "service_staffing_model": (
        "candid photograph of hospitality staff in service, warm ambient lighting, "
        "documentary-style photography with natural expressions"
    ),
    "location_strategy": (
        "exterior dusk photograph of the restaurant storefront with warm interior "
        "glow spilling onto the sidewalk, blue-hour sky, street-level perspective"
    ),
    "concept_overview": (
        "hero shot of the full restaurant interior from the entrance looking in, "
        "dramatic lighting, wide-angle architectural photography"
    ),
    "brand_positioning": (
        "overhead flat-lay of restaurant branding materials on a textured surface, "
        "soft diffused natural lighting, editorial design-studio composition"
    ),
    "our_guests": (
        "candid lifestyle photograph of guests enjoying food and drinks at the "
        "restaurant, warm ambient lighting, shallow depth of field, social atmosphere"
    ),
}


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in .env and restart the server.")
    return OpenAI(api_key=api_key)


def _build_generic_prompt(concept_description: str, framing: str) -> str:
    """Fallback prompt when the composer is unavailable."""
    return (
        f"Photorealistic photograph of a restaurant scene. "
        f"Concept: {concept_description}. "
        f"Visual focus: {framing}. "
        f"Shot on a Canon EOS R5 with a 35 mm f/1.4 lens, shallow depth of field, "
        f"natural warm ambient lighting mixed with soft directional fill light. "
        f"Professional architectural and food photography style, magazine editorial quality. "
        f"ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNS, NO LOGOS, NO WATERMARKS "
        f"anywhere in the image."
    )


def _resolve_prompt(
    *,
    concept: Optional[Dict[str, Any]],
    concept_description: str,
    section_id: str,
    section_title: str,
    framing: str,
) -> str:
    """Try the composer; fall back to generic style on any failure."""
    if concept:
        try:
            return compose_image_prompt(
                concept=concept,
                section_id=section_id,
                section_title=section_title,
                framing=framing,
            )
        except Exception as exc:
            print(f"Warning: prompt composer failed for {section_id}: {exc}. Falling back.")
    return _build_generic_prompt(concept_description, framing)


def generate_section_images(
    *,
    concept_name: str,
    concept_description: str,
    section_id: str,
    section_title: str,
    concept: Optional[Dict[str, Any]] = None,
) -> Optional[tuple[str, str]]:
    """
    Generate a photorealistic image for a section using DALL-E 3.

    Returns (image_url, alt_text) or None if this section has no image framing
    or generation fails.
    """
    framing = IMAGE_SECTIONS.get(section_id)
    if framing is None:
        return None

    prompt = _resolve_prompt(
        concept=concept,
        concept_description=concept_description,
        section_id=section_id,
        section_title=section_title,
        framing=framing,
    )

    try:
        client = _get_client()
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="hd",
            n=1,
        )
        image_url = response.data[0].url
        alt_text = f"{concept_name} - {section_title}"
        return image_url, alt_text
    except Exception as exc:
        print(f"Warning: DALL-E generation failed for {section_id}: {exc}")
        return None
