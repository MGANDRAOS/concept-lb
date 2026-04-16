"""Generate 20-30 concept-tailored facts for display during plan generation."""

from typing import Any, Dict, List

from orchestration.openai_client import call_model_json


FACTS_MODEL = "gpt-5.4-nano-2026-03-17"
FACTS_MAX_TOKENS = 1600
FACTS_COUNT = 25

_SYSTEM_PROMPT = (
    "You are a hospitality industry writer producing short, specific, "
    "conversational facts for a restaurateur who is waiting on a plan "
    "to generate. Given a restaurant concept, produce exactly {count} "
    "facts spanning a mix of: local market trivia for the concept's "
    "city; cuisine history and origin stories; industry benchmarks "
    "(margins, labor, food cost); operational insights (kitchen, "
    "service, menu design); hospitality wisdom or chef quotes; and "
    "small behind-the-scenes observations about the restaurant business. "
    "Each fact must be 1-2 sentences, ~25-45 words, factually plausible "
    "(if uncertain, phrase as an industry observation), and specific "
    "rather than generic. Vary the topics across the list - don't stack "
    "five local-market facts in a row. Return JSON exactly like: "
    "{{\"facts\": [{{\"text\": \"...\", \"topic\": \"LOCAL MARKET - BEIRUT\"}}, ...]}}. "
    "The topic tag is uppercase with dashes, short, and describes the fact's category "
    "plus an identifier like the city or cuisine name."
)


def _build_user_prompt(concept: Dict[str, Any]) -> str:
    lines = [
        "RESTAURANT CONCEPT:",
        f"- Name: {concept.get('concept_name') or 'unnamed'}",
        f"- Cuisine: {concept.get('cuisine_type') or 'unspecified'}",
        f"- One-liner: {concept.get('one_liner') or ''}",
        f"- Location: {concept.get('city') or ''}, {concept.get('country') or ''}",
        f"- Neighborhood type: {concept.get('neighborhood_type') or 'unspecified'}",
        f"- Service model: {concept.get('service_model') or 'unspecified'}",
        f"- Price: {concept.get('price_positioning') or 'unspecified'}",
    ]
    aud = concept.get("target_audience") or []
    if isinstance(aud, list) and aud:
        lines.append(f"- Target audience: {', '.join(str(x) for x in aud)}")
    brand = concept.get("brand_personality_keywords") or []
    if isinstance(brand, list) and brand:
        lines.append(f"- Brand personality: {', '.join(str(x) for x in brand)}")
    return "\n".join(lines)


def generate_facts(concept: Dict[str, Any], count: int = FACTS_COUNT) -> List[Dict[str, str]]:
    """Return a list of {text, topic} dicts. Raises on failure."""
    result = call_model_json(
        system_prompt=_SYSTEM_PROMPT.format(count=count),
        user_prompt=_build_user_prompt(concept),
        model_name=FACTS_MODEL,
        max_output_tokens=FACTS_MAX_TOKENS,
    )
    facts = result.get("facts")
    if not isinstance(facts, list) or len(facts) == 0:
        raise ValueError(f"Facts generator returned malformed response: {result!r}")
    # Normalize shape - drop any that lack text; coerce topic to string.
    normalized = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        topic = item.get("topic") or ""
        if isinstance(text, str) and text.strip():
            normalized.append({"text": text.strip(), "topic": str(topic).strip().upper()})
    if not normalized:
        raise ValueError(f"Facts generator returned no usable facts: {result!r}")
    return normalized
