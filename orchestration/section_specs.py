from typing import Dict, List, Optional


# Minimal spec fields needed for the generator.
# We'll keep it simple and add more constraints later if needed.
SECTION_SPECS = [
    # 1
    {"order": 1, "id": "cover_page", "title": "Cover Page (Concept Name + 'Restaurant Concept Development Plan')",
     "style": "paragraph+callout", "max_words": 120, "required_blocks": ["paragraph", "callout"], "conditional": None},

    # 2
    {"order": 2, "id": "mission", "title": "Mission",
     "style": "paragraph+bullets", "max_words": 160, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 3
    {"order": 3, "id": "vision", "title": "Vision",
     "style": "paragraph+bullets", "max_words": 170, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 4
    {"order": 4, "id": "concept_overview", "title": "Concept Overview",
     "style": "paragraph+bullets", "max_words": 260, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 5
    {"order": 5, "id": "location_strategy", "title": "The Location Strategy",
     "style": "paragraph+bullets+table", "max_words": 300, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None},

    # 6
    {"order": 6, "id": "environment_atmosphere", "title": "The Environment & Atmosphere",
     "style": "paragraph+bullets", "max_words": 260, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 7
    {"order": 7, "id": "brand_positioning", "title": "The Brand Positioning",
     "style": "paragraph+table+bullets", "max_words": 320, "required_blocks": ["paragraph", "table", "bullets"], "conditional": None},

    # 8
    {"order": 8, "id": "food_program", "title": "The Food Program Architecture",
     "style": "paragraph+bullets+table", "max_words": 380, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None},

    # 9
    {"order": 9, "id": "menu_structure", "title": "The Menu Structure",
     "style": "paragraph+bullets+table", "max_words": 450, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None},

    # 9.1 (conditional on morning)
    {"order": 10, "id": "menu_morning", "title": "Morning Offerings (if applicable)",
     "style": "paragraph+bullets", "max_words": 220, "required_blocks": ["paragraph", "bullets"],
     "conditional": {"field": "meal_periods", "contains": "morning"}},

    # 9.2
    {"order": 11, "id": "menu_core_dayparts", "title": "Lunch / Dinner / Late-night",
     "style": "paragraph+bullets", "max_words": 260, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 9.3
    {"order": 12, "id": "menu_signature_items", "title": "By-the-Slice / Core Items",
     "style": "paragraph+bullets+table", "max_words": 280, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None},

    # 9.4
    {"order": 13, "id": "menu_supporting_items", "title": "House Sauces / Sides / Desserts",
     "style": "bullets+table", "max_words": 240, "required_blocks": ["bullets", "table"], "conditional": None},

    # 10
    {"order": 14, "id": "beverage_program", "title": "The Beverage Program",
     "style": "paragraph+bullets", "max_words": 280, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 10.1
    {"order": 15, "id": "beverage_hot", "title": "Hot Beverages",
     "style": "bullets+table", "max_words": 200, "required_blocks": ["bullets", "table"], "conditional": None},

    # 10.2
    {"order": 16, "id": "beverage_non_alcoholic", "title": "Non-Alcoholic Beverages",
     "style": "bullets+table", "max_words": 220, "required_blocks": ["bullets", "table"], "conditional": None},

    # 10.3 (conditional on alcohol)
    {"order": 17, "id": "beverage_alcohol", "title": "Alcoholic Program (conditional – based on intake)",
     "style": "paragraph+bullets+table", "max_words": 260, "required_blocks": ["paragraph", "bullets", "table"],
     "conditional": {"field": "alcohol_flag", "equals": True}},

    # 11
    {"order": 18, "id": "equipment_requirements", "title": "Equipment Requirements",
     "style": "paragraph+table", "max_words": 320,"max_output_tokens": 1600, "required_blocks": ["paragraph", "table"], "conditional": None},

    # 12
    {"order": 19, "id": "daily_programming", "title": "Daily Programming Strategy (Morning → Night segmentation)",
     "style": "paragraph+table+bullets", "max_words": 320, "required_blocks": ["paragraph", "table", "bullets"], "conditional": None},

    # 13
    {"order": 20, "id": "service_staffing_model", "title": "The Service & Staffing Model",
     "style": "paragraph+table+bullets", "max_words": 380, "required_blocks": ["paragraph", "table", "bullets"], "conditional": None},

    # 14
    {"order": 21, "id": "our_guests", "title": "Our Guests (Target Audience Definition)",
     "style": "paragraph+bullets+callout", "max_words": 300, "required_blocks": ["paragraph", "bullets", "callout"], "conditional": None},

    # 15
    {"order": 22, "id": "swot", "title": "SWOT Analysis",
     "style": "table", "max_words": 220, "required_blocks": ["table"], "conditional": None},

    # 16
    {"order": 23, "id": "operations_overview", "title": "Operations Overview",
     "style": "paragraph+bullets", "max_words": 320, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 17
    {"order": 24, "id": "pos_profitability_framework", "title": "POS & Profitability System Framework",
     "style": "paragraph+bullets+table", "max_words": 340, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None},

    # 18
    {"order": 25, "id": "communications_strategy", "title": "Communications Strategy",
     "style": "paragraph+bullets", "max_words": 260, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 19
    {"order": 26, "id": "launch_opening_strategy", "title": "Launch & Opening Strategy",
     "style": "table+bullets", "max_words": 320, "required_blocks": ["table", "bullets"], "conditional": None},

    # 20
    {"order": 27, "id": "digital_marketing", "title": "Digital Marketing Strategy",
     "style": "paragraph+bullets", "max_words": 280, "required_blocks": ["paragraph", "bullets"], "conditional": None},

    # 21
    {"order": 28, "id": "social_media", "title": "Social Media Strategy",
     "style": "table+bullets", "max_words": 320, "required_blocks": ["table", "bullets"], "conditional": None},

    # 22
    {"order": 29, "id": "ownership_profile", "title": "Ownership Profile (Mandatory)",
     "style": "paragraph+bullets+callout", "max_words": 260, "required_blocks": ["paragraph", "bullets", "callout"], "conditional": None},

    # 23 (we will generate assumptions separately then render them as a section)
    # Section will be created by backend (not the model), so no spec here.

    # 24
    {"order": 30, "id": "closing_page", "title": "Concept LB Signature Closing Page",
     "style": "paragraph+bullets+callout", "max_words": 220, "required_blocks": ["paragraph", "bullets", "callout"], "conditional": None},
]

def should_include_section(section_spec: Dict, concept: Dict) -> bool:
    """
    Supports:
    - simple conditional: {"field":"alcohol_flag","equals":true}
    - meal_period conditional: {"field":"meal_periods","contains":"morning"}
    """
    cond: Optional[Dict] = section_spec.get("conditional")
    if not cond:
        return True

    field = cond.get("field")
    if field is None:
        return True

    if "equals" in cond:
        return concept.get(field) == cond.get("equals")

    if "contains" in cond:
        value = concept.get(field)
        if not isinstance(value, list):
            return False
        return cond.get("contains") in value

    return True