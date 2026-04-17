from orchestration.section_dependencies import downstream_of


def test_concept_overview_invalidates_many():
    stale = downstream_of("concept_overview")
    assert "location_strategy" in stale
    assert "brand_positioning" in stale
    assert "menu_structure" in stale
    assert "menu_core_dayparts" in stale  # transitive via menu_structure
    # It should not include itself
    assert "concept_overview" not in stale


def test_menu_structure_transitive_to_menu_children():
    stale = downstream_of("menu_structure")
    assert stale == {
        "menu_morning",
        "menu_core_dayparts",
        "menu_signature_items",
        "menu_supporting_items",
    }


def test_daily_programming_has_no_dependents():
    assert downstream_of("daily_programming") == set()


def test_unknown_section_returns_empty_set():
    assert downstream_of("nonexistent_section") == set()


def test_food_program_cascades_to_menus_and_equipment():
    stale = downstream_of("food_program")
    assert "menu_structure" in stale
    assert "menu_signature_items" in stale  # via menu_structure
    assert "equipment_requirements" in stale
