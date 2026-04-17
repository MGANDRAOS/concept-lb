from typing import Dict, Set


# Direct (non-transitive) dependents. Key = edited section, value = sections
# that should be flagged stale because their generated content references
# or builds on the key.
DIRECT_DEPENDENTS: Dict[str, Set[str]] = {
    "concept_overview": {
        "location_strategy",
        "environment_atmosphere",
        "brand_positioning",
        "food_program",
        "menu_structure",
        "our_guests",
        "swot",
        "ownership_profile",
    },
    "location_strategy": {
        "environment_atmosphere",
        "our_guests",
        "swot",
    },
    "environment_atmosphere": {
        "brand_positioning",
    },
    "brand_positioning": {
        "communications_strategy",
        "digital_marketing",
        "social_media",
    },
    "food_program": {
        "menu_structure",
        "menu_morning",
        "menu_core_dayparts",
        "menu_signature_items",
        "menu_supporting_items",
        "equipment_requirements",
    },
    "menu_structure": {
        "menu_morning",
        "menu_core_dayparts",
        "menu_signature_items",
        "menu_supporting_items",
    },
    "beverage_program": {
        "beverage_hot",
        "beverage_non_alcoholic",
        "beverage_alcohol",
    },
    "service_staffing_model": {
        "operations_overview",
        "pos_profitability_framework",
    },
    "our_guests": {
        "swot",
    },
}


def downstream_of(section_id: str) -> Set[str]:
    """Return the transitive closure of sections that become stale when
    `section_id` is edited. Does not include `section_id` itself."""
    stale: Set[str] = set()
    frontier = list(DIRECT_DEPENDENTS.get(section_id, set()))
    while frontier:
        current = frontier.pop()
        if current in stale:
            continue
        stale.add(current)
        frontier.extend(DIRECT_DEPENDENTS.get(current, set()))
    return stale
