"""
orchestration/market_data.py
Static F&B market benchmarks by country/city.
Used to inject local context into section generation prompts.
"""

from typing import Optional

MARKET_DATA = {
    "lebanon": {
        "_default": {
            "avg_rent_sqm_usd": {"low": 15, "mid": 30, "high": 55},
            "hourly_labor_rate_usd": {"low": 3, "mid": 5, "high": 8},
            "management_salary_range_usd": {"low": 18000, "high": 36000},
            "popular_local_ingredients": [
                "labneh", "za'atar", "sumac", "akkawi cheese", "halloumi",
                "tahini", "pomegranate molasses", "pine nuts", "fresh mint",
                "flat-leaf parsley", "lamb", "chicken shawarma spices",
                "orange blossom water", "rose water", "kaak bread"
            ],
            "dining_scene": "Lebanon has a vibrant and competitive F&B scene, particularly in Beirut. The market is characterized by a strong cafe culture, diverse international cuisines, and a growing appetite for concept-driven dining. Despite economic challenges, the restaurant industry remains resilient with new openings regularly attracting attention.",
            "licensing_notes": "Food establishment licenses are obtained through the Ministry of Tourism. Alcohol licensing requires a separate permit. The process typically takes 2-4 months.",
            "currency": "USD",
            "typical_cogs_pct": {"food": 28, "beverage": 25},
        },
        "beirut": {
            "population_context": "Beirut is the capital and largest city with a metropolitan population of approximately 2.4 million. The city is the cultural and commercial center of Lebanon with a dense concentration of restaurants, cafes, and bars particularly in areas like Gemmayzeh, Mar Mikhael, Hamra, and Achrafieh.",
            "neighborhood_types": {
                "premium": ["Gemmayzeh", "Mar Mikhael", "Saifi Village", "Downtown Beirut"],
                "mid_range": ["Hamra", "Achrafieh", "Verdun", "Badaro"],
                "emerging": ["Karantina", "Bourj Hammoud"]
            },
        },
    },
    "canada": {
        "_default": {
            "avg_rent_sqm_usd": {"low": 25, "mid": 50, "high": 90},
            "hourly_labor_rate_usd": {"low": 16, "mid": 19, "high": 25},
            "management_salary_range_usd": {"low": 55000, "high": 85000},
            "popular_local_ingredients": [
                "Ontario cheddar", "local craft beer", "maple syrup",
                "wild mushrooms", "bison", "smoked salmon",
                "locally-sourced greens", "artisanal bread"
            ],
            "dining_scene": "Canada's restaurant industry is diverse and mature, with strong farm-to-table movements and growing interest in global cuisines. Labor costs are significant due to minimum wage increases, but the market supports premium dining concepts.",
            "licensing_notes": "Business licenses are municipal. Liquor licenses are provincial (AGCO in Ontario, LCLB in BC). The process can take 3-6 months. SmartServe certification required for all alcohol servers in Ontario.",
            "currency": "CAD",
            "typical_cogs_pct": {"food": 28, "beverage": 22},
        },
        "ottawa": {
            "population_context": "The Ottawa-Gatineau area has a population of approximately 1.49 million (2021 census), growing at 8.5%. The city has a diverse population with a growing appreciation for craft food and beverage concepts. The tourism industry contributes significantly to the local economy.",
            "neighborhood_types": {
                "premium": ["ByWard Market", "Westboro", "Glebe"],
                "mid_range": ["Centretown", "Hintonburg", "Little Italy"],
                "emerging": ["Orleans", "Kanata", "Barrhaven"]
            },
        },
    },
    "uae": {
        "_default": {
            "avg_rent_sqm_usd": {"low": 40, "mid": 80, "high": 160},
            "hourly_labor_rate_usd": {"low": 4, "mid": 7, "high": 12},
            "management_salary_range_usd": {"low": 36000, "high": 72000},
            "popular_local_ingredients": [
                "saffron", "dates", "Arabic coffee", "cardamom",
                "lamb", "fresh seafood", "za'atar", "labneh",
                "rose water", "pistachio", "halloumi"
            ],
            "dining_scene": "The UAE has one of the most dynamic F&B markets globally, driven by tourism, a large expatriate population, and high disposable incomes. Competition is fierce, but well-positioned concepts can thrive. The market values experience-driven dining and Instagram-worthy presentations.",
            "licensing_notes": "Trade licenses are obtained through the Department of Economic Development. Food safety certification from the municipality is required. Alcohol licenses are available in hotels and designated areas.",
            "currency": "USD",
            "typical_cogs_pct": {"food": 30, "beverage": 24},
        },
        "dubai": {
            "population_context": "Dubai has a population of approximately 3.5 million, with over 85% expatriates. The city is a global tourism hub hosting 16+ million visitors annually. The F&B sector is highly competitive with thousands of restaurants.",
            "neighborhood_types": {
                "premium": ["DIFC", "Downtown Dubai", "Dubai Marina", "Palm Jumeirah"],
                "mid_range": ["JLT", "Business Bay", "Al Barsha", "Jumeirah"],
                "emerging": ["Al Quoz", "Dubai Hills", "Dubai Creek Harbour"]
            },
        },
    },
    "saudi_arabia": {
        "_default": {
            "avg_rent_sqm_usd": {"low": 20, "mid": 45, "high": 100},
            "hourly_labor_rate_usd": {"low": 4, "mid": 7, "high": 12},
            "management_salary_range_usd": {"low": 30000, "high": 60000},
            "popular_local_ingredients": [
                "dates", "Arabic coffee", "cardamom", "saffron",
                "lamb", "chicken", "flatbread", "tahini",
                "hummus", "za'atar", "ghee", "rose water"
            ],
            "dining_scene": "Saudi Arabia's F&B market is rapidly expanding under Vision 2030 reforms. The opening of entertainment venues and relaxation of social restrictions has fueled a dining boom, particularly in Riyadh and Jeddah. Young Saudi consumers are eager for novel dining experiences.",
            "licensing_notes": "Commercial registrations through the Ministry of Commerce. Municipal permits for food establishments. No alcohol licenses available. Saudization requirements apply to staffing.",
            "currency": "SAR",
            "typical_cogs_pct": {"food": 28, "beverage": 20},
        },
        "riyadh": {
            "population_context": "Riyadh is the capital with a population of approximately 7.6 million. The city has seen explosive growth in its dining scene, with new restaurant districts emerging. Vision 2030 investments are transforming the entertainment and hospitality landscape.",
            "neighborhood_types": {
                "premium": ["Al Olaya", "King Abdullah Financial District", "Diplomatic Quarter"],
                "mid_range": ["Al Malqa", "Al Nakheel", "Al Sahafah"],
                "emerging": ["KAFD surrounding areas", "Diriyah Gate"]
            },
        },
    },
}


def get_market_context(country: str, city: str) -> Optional[str]:
    """
    Build a market context string for prompt injection.
    Returns None if no data available for the country.
    """
    country_key = country.lower().strip().replace(" ", "_")
    city_key = city.lower().strip().replace(" ", "_")

    country_data = MARKET_DATA.get(country_key)
    if not country_data:
        return None

    # Merge _default with city-specific overrides
    defaults = country_data.get("_default", {})
    city_data = country_data.get(city_key, {})
    merged = {**defaults, **city_data}

    if not merged:
        return None

    lines = []

    rent = merged.get("avg_rent_sqm_usd")
    if rent:
        lines.append(f"- Typical rent range: ${rent['low']}-${rent['high']} per sqm/month")

    labor = merged.get("hourly_labor_rate_usd")
    if labor:
        lines.append(f"- Hourly labor rates: ${labor['low']}-${labor['high']}/hour")

    mgmt = merged.get("management_salary_range_usd")
    if mgmt:
        lines.append(f"- Management salary range: ${mgmt['low']:,}-${mgmt['high']:,}/year")

    ingredients = merged.get("popular_local_ingredients")
    if ingredients:
        lines.append(f"- Popular local ingredients: {', '.join(ingredients[:10])}")

    scene = merged.get("dining_scene")
    if scene:
        lines.append(f"- Dining scene: {scene}")

    pop = merged.get("population_context")
    if pop:
        lines.append(f"- Population & market: {pop}")

    neighborhoods = merged.get("neighborhood_types")
    if neighborhoods:
        parts = []
        for tier, names in neighborhoods.items():
            parts.append(f"  {tier}: {', '.join(names)}")
        lines.append("- Neighborhood tiers:\n" + "\n".join(parts))

    licensing = merged.get("licensing_notes")
    if licensing:
        lines.append(f"- Licensing: {licensing}")

    cogs = merged.get("typical_cogs_pct")
    if cogs:
        lines.append(f"- Typical COGS: food {cogs['food']}%, beverage {cogs['beverage']}%")

    currency = merged.get("currency")
    if currency:
        lines.append(f"- Local currency: {currency}")

    return "\n".join(lines) if lines else None
