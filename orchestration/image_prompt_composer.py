from typing import Any, Dict

from orchestration.openai_client import call_model_json


PROMPT_COMPOSER_MODEL = "gpt-5.4-nano-2026-03-17"
PROMPT_COMPOSER_MAX_TOKENS = 300

_SYSTEM_PROMPT = (
    "You are a photography art director writing prompts for DALL-E 3. "
    "Given a restaurant concept and a section-specific visual framing, "
    "produce ONE tightly-written photographic prompt that (a) honors the "
    "framing direction, (b) reflects the concept's cuisine, ambiance, "
    "location, and brand, and (c) contains no text, logos, signage, or "
    "watermarks. Return JSON: {\"prompt\": \"...\"}."
)


def _concept_brief(concept: Dict[str, Any]) -> str:
    def _join(key: str) -> str:
        value = concept.get(key) or []
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) or "unspecified"
        return str(value) or "unspecified"

    return (
        f"Concept name: {concept.get('concept_name') or 'unnamed'}\n"
        f"Cuisine: {concept.get('cuisine_type') or 'unspecified'}\n"
        f"One-liner: {concept.get('one_liner') or ''}\n"
        f"Location: {concept.get('city') or ''}, {concept.get('country') or ''}\n"
        f"Neighborhood type: {concept.get('neighborhood_type') or 'unspecified'}\n"
        f"Service model: {concept.get('service_model') or 'unspecified'}\n"
        f"Price positioning: {concept.get('price_positioning') or 'unspecified'}\n"
        f"Target audience: {_join('target_audience')}\n"
        f"Brand personality: {_join('brand_personality_keywords')}\n"
        f"Interior mood: {_join('interior_mood_keywords')}\n"
        f"Beverage direction: {concept.get('beverage_direction') or 'unspecified'}\n"
        f"Alcohol: {'yes' if concept.get('alcohol_flag') else 'no'}"
    )


def compose_image_prompt(
    *,
    concept: Dict[str, Any],
    section_id: str,
    section_title: str,
    framing: str,
) -> str:
    """
    Produce a concept-tailored DALL-E prompt for a given section.

    Raises on failure — callers must handle fallback.
    """
    user_prompt = (
        f"RESTAURANT CONCEPT:\n{_concept_brief(concept)}\n\n"
        f"SECTION: {section_title} (id: {section_id})\n"
        f"VISUAL FRAMING: {framing}\n\n"
        "Write a photographic DALL-E prompt (one paragraph, ~70-120 words) "
        "that reflects this specific concept, not a generic restaurant. "
        "Name concrete visual elements (materials, colors, food items, "
        "lighting) consistent with the cuisine and brand. End the prompt "
        "with: 'ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO SIGNS, NO "
        "LOGOS, NO WATERMARKS anywhere in the image.'"
    )

    result = call_model_json(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_name=PROMPT_COMPOSER_MODEL,
        max_output_tokens=PROMPT_COMPOSER_MAX_TOKENS,
    )

    prompt = result.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f"Composer returned malformed response: {result!r}")
    return prompt.strip()
