from unittest.mock import patch

from orchestration.normalization import normalize_intake


def _model_output_concept(**overrides):
    """A complete, schema-valid concept as the normalization MODEL might return it."""
    concept = {
        "language": "en",
        "concept_name": "Slice Society",
        "one_liner": "Modern pizzeria that serves slices besides whole pie.",
        "cuisine_type": "Pizzeria",
        "service_model": "hybrid",
        "differentiator": "Fermented dough, top quality, with a slice option.",
        "country": "Lebanon",      # model wrongly "corrects" location to Lebanon
        "city": "Beirut",          # model wrongly "corrects" location to Beirut
        "neighborhood_type": "street",
        "size_sqm": 50,
        "seating_capacity": 24,
        "alcohol_flag": False,
        "target_audience": ["Families", "Office workers", "Students"],
        "price_positioning": "affordable",
        "meal_periods": ["lunch", "dinner"],
        "competitors": [],
        "competitive_edge": "NY style which doesn't exist a lot locally.",
        "brand_personality_keywords": ["bold", "minimal"],
        "interior_mood_keywords": ["clean", "modern"],
        "beverage_direction": "juice_bar",
        "delivery_flag": True,
        "operating_hours": "12:00-23:30",
        "founder_background": "10 years in hospitality.",
        "ownership_structure": "partners",
        "budget_tier": "mid",
        "experience_level": "some",
        "confidence": {},
    }
    concept.update(overrides)
    return {"concept": concept, "inference_log": []}


def test_user_country_city_survive_normalization():
    """The normalization pass must never overwrite the location the user entered.

    Regression: a Lebanon-biased model could rewrite Bucharest/Romania to
    Beirut/Lebanon, which then pulled Lebanon market data (mentioning Beirut)
    into every generated section.
    """
    intake = {
        "concept_name": "Slice Society",
        "service_model": "hybrid",
        "country": "Romania",
        "city": "Bucharest",
    }

    with patch(
        "orchestration.normalization.call_model_json",
        return_value=_model_output_concept(country="Lebanon", city="Beirut"),
    ):
        result = normalize_intake(intake)

    assert result["concept"]["country"] == "Romania"
    assert result["concept"]["city"] == "Bucharest"


def test_location_passthrough_trims_whitespace():
    intake = {
        "concept_name": "Slice Society",
        "country": "  Romania  ",
        "city": "  Bucharest  ",
    }

    with patch(
        "orchestration.normalization.call_model_json",
        return_value=_model_output_concept(country="Lebanon", city="Beirut"),
    ):
        result = normalize_intake(intake)

    assert result["concept"]["country"] == "Romania"
    assert result["concept"]["city"] == "Bucharest"
