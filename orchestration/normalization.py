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
    
        # --- Canonicalize MODEL OUTPUT before Pydantic validation ---
    concept_out = result_dict.get("concept")
    if not isinstance(concept_out, dict):
        raise ValueError("Normalization model output missing 'concept' object")

    # language: "English" -> "en"
    lang = concept_out.get("language")
    if isinstance(lang, str):
        lang_norm = lang.strip().lower()
        if lang_norm in ("english", "en"):
            concept_out["language"] = "en"
        elif lang_norm in ("arabic", "ar"):
            concept_out["language"] = "ar"

    # service_model: "QSR" -> "qsr"
    sm = concept_out.get("service_model")
    if isinstance(sm, str):
        sm_norm = sm.strip().lower()
        mapping = {
            "qsr": "qsr",
            "quick service": "qsr",
            "quick_service": "qsr",
            "quick-service": "qsr",
            "dine in": "dine_in",
            "dine_in": "dine_in",
            "dine-in": "dine_in",
            "full service": "dine_in",
            "full_service": "dine_in",
            "hybrid": "hybrid",
        }
        if sm_norm in mapping:
            concept_out["service_model"] = mapping[sm_norm]

    # beverage_direction: map your wizard label -> schema enum
    bev = concept_out.get("beverage_direction")
    if isinstance(bev, str):
        bev_norm = bev.strip().lower()
        bev_map = {
            "coffee": "coffee_focus",
            "coffee_focus": "coffee_focus",
            "coffee-focused": "coffee_focus",
            "mocktails": "mocktails",
            "no_alcohol_cocktails": "mocktails",
            "full_bar": "full_bar",
            "bar": "full_bar",
            "alcohol": "full_bar",
            "juice": "juice_bar",
            "juice_bar": "juice_bar",
            "juice_and_sodas": "juice_bar",
            "juices_and_sodas": "juice_bar",
            "fresh_juice": "juice_bar",
        }
        if bev_norm in bev_map:
            concept_out["beverage_direction"] = bev_map[bev_norm]

    # target_audience: "Foodies, Families" -> ["Foodies", "Families"]
    ta = concept_out.get("target_audience")
    if isinstance(ta, str):
        concept_out["target_audience"] = [x.strip() for x in ta.split(",") if x.strip()]
    elif ta is None:
        concept_out["target_audience"] = []
    elif isinstance(ta, list):
        concept_out["target_audience"] = [str(x).strip() for x in ta if str(x).strip()]

    # write back (not strictly needed since dict is mutated, but explicit is nice)
    result_dict["concept"] = concept_out
    
    # experience_level: map variants -> schema enum ('new' | 'some' | 'expert')
    exp = concept_out.get("experience_level")
    if isinstance(exp, str):
        exp_norm = exp.strip().lower()

        exp_map = {
            "new": "new",
            "beginner": "new",
            "first_time_founder": "new",
            "first-time-founder": "new",
            "first time founder": "new",
            "no_experience": "new",
            "none": "new",

            "some": "some",
            "intermediate": "some",
            "some_experience": "some",
            "some experience": "some",

            "expert": "expert",
            "experienced": "expert",
            "pro": "expert",
            "veteran": "expert",
        }

        if exp_norm in exp_map:
            concept_out["experience_level"] = exp_map[exp_norm]
        
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