import json
from typing import Any, Dict

from schemas.concept_schema import NormalizationResult
from orchestration.openai_client import call_model_json


NORMALIZATION_SYSTEM_PROMPT = """
You are Concept LB, a restaurant concept development system.

TASK:
Normalize user intake into a strict Concept Object for Lebanon (currency USD context).
Return ONLY valid JSON that matches this structure:

{
  "concept": { ... all required fields ... },
  "inference_log": [
    {"field": "...", "inferred": true, "rationale": "..."}
  ]
}

RULES:
- Output JSON only. No markdown. No extra commentary.
- Do not ask questions; infer minimally if missing.
- If you infer any missing detail, add an inference_log entry.
- Keep writing short and precise. No fluff inside fields.
"""

NORMALIZATION_USER_PROMPT_TEMPLATE = """
INTAKE (raw user inputs as JSON):
{intake_json}

REQUIRED OUTPUT:
Return a JSON object with keys:
- concept
- inference_log

The concept must include:
language, concept_name, one_liner, cuisine_type, service_model, differentiator,
country, city, neighborhood_type, size_sqm, seating_capacity, alcohol_flag,
target_audience, price_positioning, meal_periods, competitors, competitive_edge,
brand_personality_keywords, interior_mood_keywords, beverage_direction, delivery_flag,
operating_hours, founder_background, ownership_structure, budget_tier, experience_level.
"""


def normalize_intake(intake: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pass A: Normalize intake into a strict Concept Object (JSON).
    Validates using Pydantic. Raises a clean error if invalid.
    """
    # If wizard posts concept fields at root, wrap them under "concept"
    if "concept" not in intake and any(
        key in intake for key in ("concept_name", "country", "service_model", "city")
    ):
        intake = {"concept": intake}
    lang = intake["concept"].get("language")
    if isinstance(lang, str):
        lang_norm = lang.strip().lower()
        if lang_norm in ("english", "en"):
            intake["concept"]["language"] = "en"
        elif lang_norm in ("arabic", "ar"):
            intake["concept"]["language"] = "ar"    
            
            
    service_model = intake["concept"].get("service_model")
    if isinstance(service_model, str):
        sm = service_model.strip().lower()
        # common variants
        if sm in ("qsr", "quick service", "quick_service", "quick-service"):
            intake["concept"]["service_model"] = "qsr"
        elif sm in ("dine in", "dine_in", "dine-in", "full service", "full_service"):
            intake["concept"]["service_model"] = "dine_in"
        elif sm in ("hybrid",):
            intake["concept"]["service_model"] = "hybrid" 
            
    raw_target = intake["concept"].get("target_audience")

    if isinstance(raw_target, str):
        intake["concept"]["target_audience"] = [x.strip() for x in raw_target.split(",") if x.strip()]
    elif raw_target is None:
        intake["concept"]["target_audience"] = []
    elif isinstance(raw_target, list):
        intake["concept"]["target_audience"] = [str(x).strip() for x in raw_target if str(x).strip()]        
                          
                 
    # Accept multiple payload shapes and force a top-level "concept"
    if "concept" not in intake or intake.get("concept") is None:
        # common alternate shapes
        if isinstance(intake.get("data"), dict) and isinstance(intake["data"].get("concept"), dict):
            intake["concept"] = intake["data"]["concept"]
        elif isinstance(intake.get("payload"), dict) and isinstance(intake["payload"].get("concept"), dict):
            intake["concept"] = intake["payload"]["concept"]
        elif isinstance(intake.get("form"), dict) and isinstance(intake["form"].get("concept"), dict):
            intake["concept"] = intake["form"]["concept"]
        else:
            raise ValueError("Missing required top-level key: concept")
    intake_json = json.dumps(intake, ensure_ascii=False)

    user_prompt = NORMALIZATION_USER_PROMPT_TEMPLATE.format(intake_json=intake_json)

    result_dict = call_model_json(
        system_prompt=NORMALIZATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_name="gpt-5.2",
        reasoning_effort="low",
        max_output_tokens=1200,
    )
    
    raw_target = intake.get("concept", {}).get("target_audience")

    if isinstance(raw_target, str):
        # Convert comma-separated string to list
        intake["concept"]["target_audience"] = [
            x.strip()
            for x in raw_target.split(",")
            if x.strip()
        ]

    elif raw_target is None:
        intake["concept"]["target_audience"] = []

    # Validate shape strictly
    validated = NormalizationResult.model_validate(result_dict)

    # Return as plain dict to keep Flask jsonify happy
    return validated.model_dump()