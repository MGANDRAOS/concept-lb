from typing import Dict, List, Optional


# Minimal spec fields needed for the generator.
# We'll keep it simple and add more constraints later if needed.
SECTION_SPECS = [
    # 1
    {"order": 1, "id": "cover_page", "title": "Cover Page (Concept Name + 'Restaurant Concept Development Plan')",
     "style": "paragraph+callout", "max_words": 120, "required_blocks": ["paragraph", "callout"], "conditional": None,
     "prompt_hint": "Short and punchy. Concept name, subtitle, one-line tagline."},

    # 2
    {"order": 2, "id": "mission", "title": "Mission",
     "style": "paragraph+bullets", "max_words": 160, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "One strong paragraph defining the core purpose. 2-3 bullet points on what makes it distinctive."},

    # 3
    {"order": 3, "id": "vision", "title": "Vision",
     "style": "paragraph+bullets", "max_words": 170, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "Forward-looking aspiration. Where does this concept aim to be in 3-5 years?"},

    # 4
    {"order": 4, "id": "concept_overview", "title": "Concept Overview",
     "style": "paragraph+bullets", "max_words": 600, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "Write 2-3 rich paragraphs. Weave in the founder's background naturally. Reference the local market opportunity. Explain what makes this concept different from existing options. Describe the full guest experience from arrival to departure. Mention operating hours, meal periods, and service model."},

    # 5
    {"order": 5, "id": "location_strategy", "title": "The Location Strategy",
     "style": "paragraph+bullets+table", "max_words": 500, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None,
     "prompt_hint": "Reference the city's population, dining scene, and real estate context. Mention specific neighborhood types suited to this concept. Include why this market has an opportunity gap. If market context data is provided, cite demographic and rent figures."},

    # 6
    {"order": 6, "id": "environment_atmosphere", "title": "The Environment & Atmosphere",
     "style": "paragraph+bullets", "max_words": 260, "required_blocks": ["paragraph", "bullets"], "conditional": None, "generate_image": True,
     "prompt_hint": "Describe the physical space: lighting, furniture, music, and how atmosphere shifts across meal periods. Make the reader visualize being inside."},

    # 7
    {"order": 7, "id": "brand_positioning", "title": "The Brand Positioning",
     "style": "paragraph+table+bullets", "max_words": 320, "required_blocks": ["paragraph", "table", "bullets"], "conditional": None,
     "prompt_hint": "Define the brand identity: color palette direction, signage style, packaging. Explain how the brand differentiates from competitors visually and emotionally."},

    # 8
    {"order": 8, "id": "food_program", "title": "The Food Program",
     "style": "paragraph+bullets+table", "max_words": 600, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None, "generate_image": True,
     "prompt_hint": "Describe the overall food strategy: cuisine philosophy, ingredient sourcing approach, how the menu spans meal periods. Weave in the founder's culinary vision. This is the narrative overview before the detailed menu pages."},

    # 9
    {"order": 9, "id": "menu_structure", "title": "The Menu Structure",
     "style": "paragraph+bullets+table", "max_words": 450, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None, "generate_image": True,
     "prompt_hint": "Overview of how the menu is organized: categories, pricing tiers, portion strategy. Include a summary table of category counts and price ranges."},

    # 9.1 (conditional on morning)
    {"order": 10, "id": "menu_morning", "title": "Morning Offerings",
     "style": "paragraph+menu_items", "max_words": 500, "required_blocks": ["paragraph", "menu_items"],
     "conditional": {"field": "meal_periods", "contains": "morning"},
     "prompt_hint": "Start with a brief paragraph about the morning concept (e.g., square tray pizzas, pastries, coffee pairings). Then generate a complete morning menu using menu_items blocks. 8-12 specific dishes with full ingredient lists. Name real cheeses, herbs, and local ingredients."},

    # 9.2
    {"order": 11, "id": "menu_core_dayparts", "title": "Lunch / Dinner / Late-Night",
     "style": "paragraph+menu_items", "max_words": 500, "required_blocks": ["paragraph", "menu_items"], "conditional": None,
     "prompt_hint": "Brief intro paragraph about daytime/evening philosophy. Then generate the full lunch/dinner menu using menu_items blocks. 12-18 dishes with ingredients. Include signature items, classics, and at least one weekly special placeholder."},

    # 9.3
    {"order": 12, "id": "menu_signature_items", "title": "Signature & Core Items",
     "style": "paragraph+menu_items+table", "max_words": 600, "required_blocks": ["paragraph", "menu_items", "table"], "conditional": None,
     "prompt_hint": "Highlight 6-10 hero dishes that define the concept. For each, provide the full dish name and ingredients via menu_items block. Include a table with estimated price points and food cost targets."},

    # 9.4
    {"order": 13, "id": "menu_supporting_items", "title": "House Sauces / Sides / Desserts",
     "style": "menu_items+table", "max_words": 400, "required_blocks": ["menu_items", "table"], "conditional": None,
     "prompt_hint": "Generate complete lists of house sauces (6+), salads/sides (4+), and desserts (2+) using menu_items blocks. Include a table summarizing categories and item counts."},

    # 10
    {"order": 14, "id": "beverage_program", "title": "The Beverage Program",
     "style": "paragraph+bullets", "max_words": 280, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "Narrative overview of the full beverage strategy: how it complements the food, how it shifts through the day (coffee morning, sodas lunch, cocktails evening). Reference sourcing philosophy."},

    # 10.1
    {"order": 15, "id": "beverage_hot", "title": "Hot Beverages",
     "style": "menu_items+bullets", "max_words": 350, "required_blocks": ["menu_items", "bullets"], "conditional": None,
     "prompt_hint": "List specific hot drinks using menu_items block: espresso, americano, latte, cappuccino, teas, etc. Mention local coffee roasters or sourcing style. Include sizes if relevant."},

    # 10.2
    {"order": 16, "id": "beverage_non_alcoholic", "title": "Non-Alcoholic Beverages",
     "style": "menu_items+bullets", "max_words": 350, "required_blocks": ["menu_items", "bullets"], "conditional": None,
     "prompt_hint": "List specific non-alcoholic drinks using menu_items: sodas, juices, sparkling water, mocktails. Name specific brands or styles (e.g., Italian Chinotto, fresh-pressed juices)."},

    # 10.3 (conditional on alcohol)
    {"order": 17, "id": "beverage_alcohol", "title": "Alcoholic Beverage Program",
     "style": "paragraph+menu_items+table", "max_words": 500, "required_blocks": ["paragraph", "menu_items", "table"],
     "conditional": {"field": "alcohol_flag", "equals": True},
     "prompt_hint": "Generate cocktails (4-6 with full recipes), wines (6+ specific labels with winery names), and beers (6+ specific local/craft options with brewery names). Use menu_items blocks. Include a weekly special placeholder. Add a table summarizing beverage categories and counts."},

    # 11
    {"order": 18, "id": "equipment_requirements", "title": "Equipment Requirements",
     "style": "paragraph+bullets", "max_words": 500, "max_output_tokens": 1600, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "List every individual piece of equipment as a flat bulleted list of 30-50 items. Include type/model context (e.g., 'Deck Oven or Rotating Pizza Oven', 'Alto Shaam Holding Cabinet'). Organize by area: Kitchen, Bar, Front of House, Storage, Sanitation."},

    # 12
    {"order": 19, "id": "daily_programming", "title": "Daily Programming Strategy",
     "style": "paragraph+table+bullets", "max_words": 500, "required_blocks": ["paragraph", "table", "bullets"], "conditional": None,
     "prompt_hint": "Create a time-of-day breakdown table: Morning, Lunch, Afternoon, Evening, Late Night. For each period describe: atmosphere/music, lighting, menu focus, target guest type. Match the format of a professional day-programming grid."},

    # 13
    {"order": 20, "id": "service_staffing_model", "title": "The Service & Staffing Model",
     "style": "paragraph+table+bullets", "max_words": 600, "required_blocks": ["paragraph", "table", "bullets"], "conditional": None, "generate_image": True,
     "prompt_hint": "Describe the service philosophy (how it differentiates from fast food). Detail staff roles: GM, kitchen manager, FOH staff, BOH staff. Include a table of positions with shift hours. Mention training programs and ongoing development."},

    # 14
    {"order": 21, "id": "our_guests", "title": "Our Guests",
     "style": "paragraph+bullets+callout", "max_words": 300, "required_blocks": ["paragraph", "bullets", "callout"], "conditional": None,
     "prompt_hint": "Define 3-4 guest personas with demographics and dining occasions. Explain how the concept appeals to each. Reference the local market and walk-by traffic potential."},

    # 15
    {"order": 22, "id": "swot", "title": "SWOT Analysis",
     "style": "table", "max_words": 500, "required_blocks": ["table"], "conditional": None,
     "prompt_hint": "Generate a detailed SWOT with 4-6 specific points per quadrant. Reference specific competitor types and local market dynamics. Be honest about weaknesses and threats — this builds credibility with investors."},

    # 16
    {"order": 23, "id": "operations_overview", "title": "Operations Overview",
     "style": "paragraph+bullets", "max_words": 500, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "Cover: recipe documentation and costing software, inventory control procedures, labor management software, training materials. Name specific industry tools (e.g., 7Shifts, MarketMan, Navi). Be operationally specific."},

    # 17
    {"order": 24, "id": "pos_profitability_framework", "title": "POS & Profitability System",
     "style": "paragraph+bullets+table", "max_words": 340, "required_blocks": ["paragraph", "bullets", "table"], "conditional": None,
     "prompt_hint": "Explain the POS system strategy and how it integrates with recipe costing, inventory, and labor scheduling. Describe the analytical tools for profitability optimization."},

    # 18
    {"order": 25, "id": "communications_strategy", "title": "Communications Strategy",
     "style": "paragraph+bullets", "max_words": 260, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "List pre-opening brand development activities: brand identity docs, website, social media setup, content calendar, photography/videography plans."},

    # 19
    {"order": 26, "id": "launch_opening_strategy", "title": "Launch & Opening Strategy",
     "style": "table+bullets", "max_words": 320, "required_blocks": ["table", "bullets"], "conditional": None,
     "prompt_hint": "Describe soft opening strategy: friends & family events, community engagement, influencer nights. Include a timeline table for pre-opening activities (8-12 weeks out to opening day)."},

    # 20
    {"order": 27, "id": "digital_marketing", "title": "Digital Marketing Strategy",
     "style": "paragraph+bullets", "max_words": 280, "required_blocks": ["paragraph", "bullets"], "conditional": None,
     "prompt_hint": "Cover: professional photography, Google My Business, local SEO, review platform optimization, email marketing, delivery platform presence."},

    # 21
    {"order": 28, "id": "social_media", "title": "Social Media Strategy",
     "style": "table+bullets", "max_words": 320, "required_blocks": ["table", "bullets"], "conditional": None,
     "prompt_hint": "Cover Instagram, TikTok, Facebook strategies. Include content types (reels, stories, behind-the-scenes). Mention influencer partnerships, branded hashtags, user-generated content encouragement."},

    # 22
    {"order": 29, "id": "ownership_profile", "title": "Ownership Profile",
     "style": "paragraph+bullets+callout", "max_words": 260, "required_blocks": ["paragraph", "bullets", "callout"], "conditional": None,
     "prompt_hint": "Present the founder's background, key skills, and relevant experience. Use a professional tone as if a consultant is introducing their client to investors. Include a callout box with key skills/expertise list."},

    # 23
    {"order": 30, "id": "closing_page", "title": "Closing Page",
     "style": "paragraph+callout", "max_words": 120, "required_blocks": ["paragraph", "callout"], "conditional": None,
     "prompt_hint": "Simple thank-you message. Concept name. Brief forward-looking statement."},
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