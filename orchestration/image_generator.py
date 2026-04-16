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

    prompt = (
        f"Photorealistic photograph of a restaurant scene. "
        f"Concept: {concept_description}. "
        f"Visual focus: {style}. "
        f"Shot on a Canon EOS R5 with a 35 mm f/1.4 lens, shallow depth of field, "
        f"natural warm ambient lighting mixed with soft directional fill light. "
        f"Professional architectural and food photography style, magazine editorial quality, "
        f"8K resolution, hyper-detailed textures and materials. "
        f"ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNS, NO LOGOS, NO WATERMARKS, "
        f"NO TYPOGRAPHY, NO WRITING OF ANY KIND anywhere in the image."
    )

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
    
    # Map section IDs to photorealistic photography direction
    IMAGE_SECTIONS = {
        "environment_atmosphere": (
            "wide-angle interior photograph of an upscale dining room with warm moody lighting, "
            "elegant furniture, textured walls, candle glow on table settings, bokeh background, "
            "golden-hour window light streaming in"
        ),
        "food_program": (
            "close-up overhead food photography of beautifully plated dishes on a dark slate table, "
            "fresh ingredients, vibrant colors, steam rising, professional culinary presentation, "
            "shallow depth of field, studio strobe accent lighting"
        ),
        "menu_structure": (
            "lifestyle flat-lay photograph of artfully arranged dishes and fresh raw ingredients "
            "on a rustic wooden surface, colorful garnishes, natural side lighting, "
            "editorial food-magazine composition"
        ),
        "service_staffing_model": (
            "candid photograph of professional hospitality staff in a fine-dining restaurant, "
            "crisp uniforms, warm ambient lighting, elegant table service in action, "
            "documentary photography style, natural expressions"
        ),
        "location_strategy": (
            "exterior dusk photograph of a modern restaurant storefront with large glass windows, "
            "warm interior glow spilling onto the sidewalk, blue-hour sky, street-level perspective, "
            "architectural photography with leading lines"
        ),
        "concept_overview": (
            "hero shot of the full restaurant interior from the entrance looking in, "
            "dramatic lighting, open kitchen visible in background, curated decor details, "
            "wide-angle architectural photography with rich warm tones"
        ),
        "brand_positioning": (
            "overhead flat-lay photograph of restaurant branding materials on a marble surface, "
            "elegant menu cards, branded takeout packaging, business cards, napkins with logo, "
            "design studio aesthetic, soft diffused natural lighting, editorial composition"
        ),
        "our_guests": (
            "candid lifestyle photograph of diverse groups of friends enjoying food and drinks "
            "at a stylish restaurant, warm ambient lighting, natural laughter, shared plates on table, "
            "shallow depth of field, social dining atmosphere, documentary style"
        ),
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
