import os
import pytest


@pytest.fixture
def fake_concept():
    """A minimal but realistic concept dict for tests."""
    return {
        "concept_name": "Fig & Fire",
        "cuisine_type": "Neapolitan pizza & natural wine",
        "one_liner": "Wood-fired pies and a tight natural-wine list, in a converted garage.",
        "city": "Beirut",
        "country": "Lebanon",
        "price_positioning": "mid",
        "neighborhood_type": "street",
        "service_model": "dine_in",
        "target_audience": ["young professionals", "wine enthusiasts"],
        "brand_personality_keywords": ["rustic", "unpretentious", "warm"],
        "interior_mood_keywords": ["exposed brick", "candlelight", "open kitchen"],
        "beverage_direction": "full_bar",
        "alcohol_flag": True,
    }


@pytest.fixture(autouse=True)
def _no_real_openai_key(monkeypatch):
    """Prevent accidental real API calls in unit tests by scrubbing the key."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
