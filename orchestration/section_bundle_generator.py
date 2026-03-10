import json
from typing import Any, Dict, List

from orchestration.openai_client import call_model_json
from orchestration.repair import repair_json
from orchestration.image_generator import generate_section_images


BUNDLE_SYSTEM_PROMPT = """
You are Concept LB, a restaurant concept development system.

TASK:
Generate MULTIPLE requested sections for a restaurant concept plan in ONE response.

STRICT OUTPUT RULES:
- Return ONLY valid JSON. No markdown. No extra text.
- Output must match ONE of these shapes:

A) Normal bundle:
{
  "sections": [
    {
      "id": "...",
      "title": "...",
      "blocks": [
        { "type": "paragraph", "text": "..." },
        { "type": "bullets", "items": ["...", "..."] },
        { "type": "callout", "title": "...", "text": "..." },
        { "type": "table", "columns": ["..."], "rows": [["..."]] }
      ]
    }
  ]
}

B) Bundle WITH assumptions:
{
  "sections": [ ... ],
  "assumptions_table": [
    { "label": "...", "value": "...", "explanation": "..." }
  ],
  "disclaimer": "..."
}

CONTENT RULES:
- For EACH section:
  - title MUST match the spec title EXACTLY.
  - id MUST match the spec id EXACTLY.
  - Include ALL required block types listed in the spec.
  - Do NOT reference other sections.
  - Do NOT mention AI or prompts.
- Keep content consultant-grade and structured.
- If concept.derived_financials.outputs is present:
  - Use those numbers exactly for any revenue/margin/breakeven mentions.
  - Do NOT invent or recompute alternative totals.
  - If an output is null, state it cannot be computed yet due to missing inputs.
""".strip()


BUNDLE_USER_PROMPT_TEMPLATE = """
CONCEPT_OBJECT (JSON):
{concept_json}

SECTION_SPECS_LIST (JSON array):
{specs_json}

INSTRUCTIONS:
- Generate ALL sections in SECTION_SPECS_LIST.
- Output sections in the SAME ORDER as provided.
- Respect max_words per section.
{assumptions_instruction}
""".strip()



def _validate_required_blocks(section_spec: Dict[str, Any], section_dict: Dict[str, Any]) -> None:
    blocks = section_dict.get("blocks", [])
    present_types = {b.get("type") for b in blocks if isinstance(b, dict)}

    for required in section_spec.get("required_blocks", []):
        if required not in present_types:
            raise ValueError(
                f"Section '{section_spec['id']}' missing required block '{required}'. "
                f"Present: {sorted(list(present_types))}"
            )


def generate_sections_bundle(
    concept: Dict[str, Any],
    section_specs: List[Dict[str, Any]],
    *,
    include_assumptions: bool,
    model_name: str = "gpt-5.2",
    max_output_tokens: int = 3200,
    generate_images: bool = True,
) -> Dict[str, Any]:

    concept_json = json.dumps(concept, ensure_ascii=False)
    
    derived_outputs = (concept.get("derived_financials") or {}).get("outputs") or {}
    if isinstance(derived_outputs, dict) and derived_outputs:
        concept_json = (
            "DETERMINISTIC FINANCIAL OUTPUTS (use exactly if present):\n"
            + json.dumps(derived_outputs, ensure_ascii=False)
            + "\n\n"
            + concept_json
        )
    
    specs_json = json.dumps(section_specs, ensure_ascii=False)
    
    # Compact anchors summary (helps the model not miss key numeric inputs)
    confidence = concept.get("confidence") or {}
    anchors_summary_lines = ["FINANCIAL ANCHORS SUMMARY (respect these if provided):"]

    def _src(key: str) -> str:
        return str(confidence.get(key, "ai_assumed"))

    def _line(key: str, label: str, source_key: str = None) -> None:
        v = concept.get(key, None)
        sk = source_key or key
        if v is None:
            anchors_summary_lines.append(f"- {label}: UNKNOWN (source={_src(sk)})")
        else:
            anchors_summary_lines.append(f"- {label}: {v} (source={_src(sk)})")

    _line("expected_daily_orders", "Expected daily orders")
    _line("avg_ticket_usd", "Average ticket (USD)")
    _line("monthly_rent_usd", "Monthly rent (USD)")
    _line("capex_budget_usd", "Capex budget (USD)")
    _line("staff_model", "Staff model")
    _line("target_cogs_pct", "Target COGS %")
    _line("kitchen_type", "Kitchen type")
    _line("operating_days_per_week", "Operating days/week")
    _line("alcohol_license_status", "Alcohol license status")
    _line("sales_mix_dinein_pct", "Sales mix dine-in %", source_key="sales_mix")
    _line("sales_mix_takeaway_pct", "Sales mix takeaway %", source_key="sales_mix")
    _line("sales_mix_delivery_pct", "Sales mix delivery %", source_key="sales_mix")

    anchors_block = "\n".join(anchors_summary_lines)
    anchors_summary_lines.append("IMMUTABLE VALUES: Any field marked user_provided must be copied exactly as-is.")
    
    assumptions_instruction = ""
    if include_assumptions:
        assumptions_instruction = """
        Also include assumptions_table and disclaimer in the SAME JSON response.

        CRITICAL: Use the FINANCIAL ANCHORS inside CONCEPT_OBJECT (if present).
            - If confidence for a field = "user_provided":
            • You MUST use the exact numeric/value given.
            • You MUST NOT change it.
            • You MUST NOT reinterpret it.
            • You MUST NOT upscale or adjust it.
            • You MUST include it in assumptions_table exactly as given.
        - You may only assume fields where:
        • value is null OR
        • confidence is "user_unknown" OR
        • confidence is "ai_assumed".
  - In assumptions_table, explicitly label user-provided anchors as "User provided" in the explanation.

        Assumptions must cover (ONLY if missing in the concept object):
        - Rent (monthly_rent_usd)
        - Daily orders (expected_daily_orders)
        - Average ticket (avg_ticket_usd)
        - Labor/salaries (staff_model or inferred)
        - Utilities
        - Marketing
        - Packaging
        - Equipment range (capex_budget_usd if missing, otherwise reference it)
        - Typical operating ratios (target_cogs_pct / channel mix)

        Use realistic Lebanon-calibrated USD ranges.
        Do NOT claim real market citations.eal market citations.
        """

    user_prompt = BUNDLE_USER_PROMPT_TEMPLATE.format(
        concept_json=f"{anchors_block}\n\n{concept_json}",
        specs_json=specs_json,
        assumptions_instruction=assumptions_instruction,
    )

    # Attempt 1
    try:
        result = call_model_json(
            system_prompt=BUNDLE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_name=model_name,
            reasoning_effort=None,
            max_output_tokens=max_output_tokens,
        )
    except Exception:
        # Attempt 2: slightly larger token budget
        result = call_model_json(
            system_prompt=BUNDLE_SYSTEM_PROMPT + "\n\nIMPORTANT: Keep JSON compact.",
            user_prompt=user_prompt,
            model_name=model_name,
            reasoning_effort=None,
            max_output_tokens=max(max_output_tokens, 4000),
        )

    # Repair if shape broken
    if not isinstance(result, dict) or "sections" not in result:
        expected_hint = """
Expected JSON:
{
  "sections": [ { "id":"...","title":"...","blocks":[...] } ],
  "assumptions_table": [ { "label":"...","value":"...","explanation":"..." } ],
  "disclaimer": "..."
}
- sections must be non-empty list
- titles and ids must match specs
"""
        result = repair_json(
            broken_output="Previous output invalid. Regenerate valid JSON bundle.",
            expected_hint=expected_hint,
            model_name=model_name,
        )

    sections = result.get("sections")
    
    expected_ids = [s["id"] for s in section_specs]
    returned_ids = [s.get("id") for s in sections]

    if returned_ids != expected_ids:
        raise ValueError(
            f"Section order mismatch. Expected {expected_ids}, got {returned_ids}"
        )
        
    if not isinstance(sections, list) or len(sections) == 0:
        raise ValueError("Bundle output missing non-empty 'sections'.")

    # Validate each section
    spec_by_id = {s["id"]: s for s in section_specs}

    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Each section must be an object.")

        section_id = section.get("id")
        if section_id not in spec_by_id:
            raise ValueError(f"Unexpected section id: {section_id}")

        spec = spec_by_id[section_id]

        if section.get("title") != spec.get("title"):
            raise ValueError(
                f"Title mismatch for '{section_id}'. "
                f"Expected '{spec.get('title')}', got '{section.get('title')}'."
            )

        _validate_required_blocks(spec, section)

    # Validate assumptions if requested
    if include_assumptions:
        table = result.get("assumptions_table")
        disclaimer = result.get("disclaimer")

        if not isinstance(table, list) or len(table) < 6:
            raise ValueError("Assumptions table missing or too small.")
        
        # If anchors were provided, ensure the assumptions table acknowledges at least one of them
        anchors_present = any(concept.get(k) is not None for k in [
            "expected_daily_orders", "avg_ticket_usd", "monthly_rent_usd", "capex_budget_usd"
        ])
        if anchors_present:
            joined = " ".join(
                (str(r.get("label", "")) + " " + str(r.get("value", "")) + " " + str(r.get("explanation", "")))
                for r in table if isinstance(r, dict)
            ).lower()
            if not any(x in joined for x in ["daily orders", "ticket", "rent", "capex", "cogs", "sales mix"]):
                raise ValueError("Assumptions table does not acknowledge provided anchors.")
        if not isinstance(disclaimer, str) or not disclaimer.strip():
            raise ValueError("Disclaimer missing.")
        
    if len(result["sections"]) != len(section_specs):
        raise ValueError(
            f"Model returned {len(result['sections'])} sections but expected {len(section_specs)}."
        )    

    # Generate images for eligible sections
    if generate_images:
        concept_name = concept.get("concept_name", "Restaurant Concept")
        concept_description = concept.get("concept_description", "")
        
        spec_by_id = {s["id"]: s for s in section_specs}
        
        for section in result["sections"]:
            section_id = section.get("id")
            section_title = section.get("title", "")
            spec = spec_by_id.get(section_id)
            
            # Check if this section should have an image generated
            if spec and spec.get("generate_image", False):
                image_data = generate_section_images(
                    concept_name=concept_name,
                    concept_description=concept_description,
                    section_id=section_id,
                    section_title=section_title,
                )
                
                if image_data:
                    image_url, alt_text = image_data
                    # Insert image block at the beginning of the section
                    image_block = {
                        "type": "image",
                        "url": image_url,
                        "alt_text": alt_text,
                        "caption": f"Visual representation: {section_title}",
                    }
                    section["blocks"].insert(0, image_block)

    return result