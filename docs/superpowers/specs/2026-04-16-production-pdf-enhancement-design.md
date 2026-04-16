# Production PDF Enhancement - Design Spec

**Date:** 2026-04-16
**Status:** Draft
**Scope:** 4 priorities to bring AI-generated business plans to professional consulting quality

---

## Context

Concept LB generates F&B business plans via AI. The benchmark is a $40K professional business plan produced by The Fifteen Group (Canadian hospitality consultancy) for "Slice Society" — a 34-page business plan + 12-page financial model.

Current gaps: the AI output is ~1/3 the content depth, uses a dark web-UI theme for PDF export (not print-ready), has no financial model document, and prompts produce generic rather than consultant-grade content.

**Decisions made:**
- PDF style: Match the Slice Society professional format (white, corporate, sidebar branding)
- Menu depth: Generate full dishes with ingredient descriptions
- Financial model: Separate PDF deliverable
- PDF engine: Keep Playwright, build a print-optimized HTML template

---

## P0: PDF Template Overhaul

### New Files
- `templates/plan_pdf.html` — print-optimized PDF template (white theme)
- `templates/_blocks_pdf.html` — print-optimized block rendering macros

Existing `plan_view.html` and `_blocks.html` remain untouched for web viewing.

### Layout Specification

**Page setup:**
- A4 format (210mm x 297mm)
- Margins: 25mm top, 20mm left/right, 25mm bottom
- White background, dark text (#1a1a1a)

**Typography:**
- Headings: Georgia or serif fallback, dark color
- Body: System sans-serif (Segoe UI, Helvetica, Arial), 11pt equivalent, line-height 1.6
- Tables: 10pt, tighter line-height

**Every page elements:**
- Sidebar: Concept name rotated 90° on right edge, light gray, every page via CSS `position: fixed`
- Page numbers: Bottom center via CSS counter (`counter-increment: page`)

**Cover page (page 1):**
- Concept name large, centered
- "Business Plan" subtitle
- Date
- Accent color block or bar (derived from brand, default: professional blue)
- `page-break-after: always`

**Table of Contents (page 2):**
- Auto-generated from section titles in the template (Jinja2 loop)
- Section name + page reference (approximate — CSS counters)
- `page-break-after: always`

**Section pages:**
- Each major section: `page-break-before: always`
- Section title: Large serif heading with left accent bar
- Content flows naturally across pages within a section
- Images: Full-width with 8px margin, no rounded corners, optional caption below

**Tables:**
- Clean 1px borders (#ddd)
- Header row: Light gray background (#f5f5f5), bold
- Alternating row shading (optional, subtle)
- Dollar values right-aligned
- Percentage values right-aligned

**Menu pages:**
- Dish names: UPPERCASE, bold
- Ingredients: Normal case, comma-separated below dish name
- Organized by category with category headers
- Two-column layout where appropriate for space efficiency

### Page Structure (Target ~30-34 pages)

| Page(s) | Content |
|---------|---------|
| 1 | Cover page |
| 2 | Table of Contents |
| 3 | Mission & Vision |
| 4-5 | Concept Overview |
| 6 | The Location |
| 7 | The Environment (with AI image) |
| 8 | The Brand |
| 9 | The Food Program (with AI image) |
| 10 | Menu - Morning Offerings (conditional) |
| 11-12 | Menu - Lunch/Dinner/Late-Night |
| 13 | Menu - Sauces/Sides/Desserts |
| 14 | The Beverage Program |
| 15 | Hot Beverages |
| 16 | Non-Alcoholic Beverages |
| 17 | Cocktails/Wine/Beer (conditional on alcohol_flag) |
| 18 | Equipment Requirements |
| 19 | Daily Programming |
| 20 | Service & Staffing (with AI image) |
| 21 | Our Guests |
| 22-23 | SWOT Analysis |
| 24 | Operations Overview |
| 25 | POS & Profitability |
| 26 | Communications Strategy |
| 27 | Launch & Opening Strategy |
| 28 | Digital Marketing |
| 29 | Social Media |
| 30 | Ownership Profile |
| 31 | Closing Page |

### Implementation in app.py

- New route or modification to existing: `GET /plans/<plan_id>/export/pdf`
- Render `plan_pdf.html` instead of `plan_view.html` for PDF export
- Same Playwright pipeline: `set_content()` → inject print CSS → `page.pdf()`
- Render `plan_pdf.html` on-demand from plan JSON at export time (no need to cache a second HTML column — plan JSON is already persisted)

### CSS Print Rules

```css
@page {
  size: A4;
  margin: 25mm 20mm 25mm 20mm;
}

@page :first {
  margin: 0; /* cover page is full-bleed */
}

body {
  background: white;
  color: #1a1a1a;
  font: 11pt/1.6 'Segoe UI', Helvetica, Arial, sans-serif;
}

.section {
  page-break-before: always;
}

.sidebar-brand {
  position: fixed;
  right: 5mm;
  top: 50%;
  transform: rotate(90deg);
  font-size: 9pt;
  color: #ccc;
  letter-spacing: 2px;
  text-transform: uppercase;
}

/* Page numbers via CSS counter */
@page {
  @bottom-center {
    content: counter(page);
    font-size: 9pt;
    color: #999;
  }
}
```

Note: Chromium's `@page` margin box support is limited. If `@bottom-center` doesn't work, fall back to a fixed-position footer element with JavaScript-injected page numbers, or use Playwright's `headerTemplate`/`footerTemplate` options in `page.pdf()` which support page number injection natively.

---

## P1: Content Depth Increase

### Section Spec Changes (section_specs.py)

| Section ID | Current max_words | New max_words |
|-----------|------------------|---------------|
| concept_overview | 260 | 600 |
| location_strategy | 300 | 500 |
| food_program | 380 | 600 |
| menu_morning | 220 | 500 |
| menu_core_dayparts | 260 | 500 |
| menu_signature_items | 280 | 600 |
| menu_supporting_items | 240 | 400 |
| beverage_hot | 200 | 350 |
| beverage_non_alcoholic | 220 | 350 |
| beverage_alcohol | 260 | 500 |
| equipment_requirements | 320 | 500 |
| daily_programming | 320 | 500 |
| service_staffing_model | 380 | 600 |
| swot | 220 | 500 |
| operations_overview | 320 | 500 |

All other sections remain unchanged.

**Total word budget:** ~5,500 → ~10,500

### Token Limit Changes (section_bundle_generator.py)

- `max_tokens` per chunk: 3200 → 8000 (normal), 4200 → 10000 (with assumptions)
- May need to reduce `chunk_size` from 6 to 4 sections per chunk to stay within output limits
- Increase `max_workers` consideration: 3 → 4 if generation time becomes an issue

### New Block Type: menu_items

Add a new block type to `_blocks.html` and `_blocks_pdf.html`:

```json
{
  "type": "menu_items",
  "category": "BY THE SLICE PIZZA",
  "items": [
    {"name": "MARGHERITA", "description": "Basil, Fresh Mozzarella, Tomato Sauce"},
    {"name": "HARISSA CHICKEN", "description": "Moroccan Spiced Chicken Breast, Onions, Peppers, Mozzarella, Feta, Vodka Sauce"}
  ]
}
```

This enables proper menu formatting in both web and PDF views — dish names bold/uppercase, descriptions below.

### Prompt Additions for Menu Sections

Add to system prompt for menu-related sections:

```
MENU SECTION RULES:
- Generate a complete menu with specific dishes.
- Each dish MUST have: a name (creative, appropriate to the cuisine) and a comma-separated ingredient list.
- Use the "menu_items" block type with "category" and "items" array.
- Each item has "name" (uppercase) and "description" (ingredients).
- Generate 8-15 dishes per meal period.
- Dishes must reflect the cuisine type and incorporate local ingredients from the concept's country/region.
- Name specific cheeses, herbs, proteins, sauces, and produce — not generic terms.
- Include at least one weekly special placeholder per category.
```

### Prompt Additions for Other Deep Sections

**Equipment:**
```
List every individual piece of equipment as a flat bulleted list of 30-50 items.
Include type/model context where relevant (e.g., "Deck Oven or Rotating Pizza Oven", "Alto Shaam Holding Cabinet").
Organize by area: Kitchen, Bar, Front of House, Storage, Sanitation.
```

**SWOT:**
```
Generate a detailed SWOT analysis spanning 4 quadrants.
Each quadrant must have 4-6 specific points.
Reference specific competitors by type (e.g., "chain pizzerias", "local artisanal competitors").
Reference the specific city/market context from the concept.
```

**Location:**
```
Reference the city's population context, dining scene characteristics, and real estate landscape.
Mention specific neighborhood types that would suit this concept.
Explain why this market has an opportunity gap for this concept type.
If real demographic data is available in the market context, cite it.
```

### Pydantic Schema Update

Add `MenuItemsBlock` to the block union in the schema:

```python
class MenuItem(BaseModel):
    name: str
    description: str

class MenuItemsBlock(BaseModel):
    type: Literal["menu_items"]
    category: str
    items: List[MenuItem]
```

---

## P2: Financial Model Generator

### New Files
- `orchestration/financial_model_generator.py` — core calculations + AI narrative
- `templates/financial_pdf.html` — print template for financial model PDF
- New route: `GET /plans/<plan_id>/export/financial-pdf`

### New Wizard Inputs (Step 5 expansion)

Add to the financial anchors step:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `opening_budget_usd` | number | null | Total investment (e.g., $500,000) |
| `funding_equity_pct` | number | 50 | % funded by equity |
| `funding_loan_pct` | number | 50 | % funded by loans |
| `avg_check_morning` | number | null | Morning average check per person |
| `avg_check_daytime` | number | null | Daytime average check per person |
| `avg_check_evening` | number | null | Evening average check per person |
| `revenue_growth_pct` | number | 3 | Year-over-year revenue growth % |
| `ramp_up_months` | number | 4 | Months to reach steady state |
| `ramp_start_pct` | number | 60 | Starting % of steady-state revenue |

These are optional — if not provided, the system uses sensible defaults or derives from existing `avg_ticket_usd`.

### Financial Model Calculations

All deterministic. No AI for numbers.

#### 1. Opening Budget Breakdown

If `opening_budget_usd` is provided, allocate by industry-standard percentages:

| Category | Default % | Items |
|----------|-----------|-------|
| Building (leasehold improvements) | 33% | Interior build-out, hood/venting, design fees |
| Equipment/Supplies | 36% | Kitchen equipment, bar equipment, furniture, POS, signs, A/V |
| Operating Supplies | 7% | Smallwares, paper, linen, menus, office |
| Pre-Opening Expenses | 11% | Management labor, training labor, training supplies, recruitment |
| Marketing | 2% | Media/PR, website, brand development |
| Working Capital | 6% | Food inventory, alcohol inventory, cash floats |
| Miscellaneous/Financing | 6% | Licensing, legal, rent deposit, utility deposits |

Percentages adjustable based on concept type (QSR needs less build-out, full-service needs more).

#### 2. Revenue Model

**Weekly covers by day of week:**
- Derive from `expected_daily_orders` distributed across week (Mon-Sun pattern)
- Split by meal period using `meal_periods` from intake
- Apply `avg_check_morning/daytime/evening` per period

**Revenue split by category:**
- Food: 76% (default, adjustable by concept type)
- Minerals/Soft drinks: 12%
- Liquor: 4% (0% if no alcohol)
- Wine: 4% (0% if no alcohol)
- Beer: 4% (0% if no alcohol)

#### 3. Ramp-Up Model

Year 1 monthly revenue:
- Month 1: `ramp_start_pct`% of steady state (default 60%)
- Month 2: Interpolate toward 100%
- Month 3: Interpolate toward 100%
- Month 4: 95-100% of steady state
- Months 5-13: Steady state with seasonal variation (optional)

COGS ramp-up: 130% of target in month 1, normalizing by month 4.

#### 4. Product Cost by Category

| Category | Target COGS % |
|----------|--------------|
| Food | 27% |
| Minerals | 30% |
| Liquor | 22% |
| Wine | 32% |
| Beer | 32% |

Override with `target_cogs_pct` if user-provided (applies to food category).

#### 5. Wages

**Management:** Derive from `staff_model`:
- lean: 1 GM ($60K-$75K depending on country)
- standard: 1 GM + 1 Kitchen Manager ($150K total)
- full: 1 GM + 1 KM + 1 Bar Manager ($225K total)

**Hourly labor:** As % of revenue by industry standard:
- FOH: 10-12% of revenue
- BOH: 17-20% of revenue
- Benefits/allowances: 7% of wage costs

#### 6. Operating Costs (as % of revenue)

| Item | % of Revenue |
|------|-------------|
| Smallwares/Glasswares | 0.5% |
| Paper Products | 0.3% |
| Credit Card Commissions | 1.8% (based on 60% card payments) |
| Linen/Uniform | 0.2% |
| Cleaning/Dishwasher | 0.4% |
| Marketing | 1.5% |
| Telephone | fixed $200/month |
| Repairs & Maintenance | 0.5% (Year 1), 1.0% (Year 2+) |
| Office/POS Supplies | 0.2% |
| Waste Removal | fixed $300/month |
| QSAs (giveaways) | 0.4% |
| Equipment Rental | fixed $500/month |

#### 7. Fixed Costs

- Rent: from `monthly_rent_usd` or derived from `size_sqm * rent_per_sqm / 12`
- Insurance: ~1.5% of revenue (or $500-$1500/month by size)
- Utilities: ~2% of revenue

#### 8. Year 1 Income Statement (13 four-week periods)

The F&B industry standard uses 13 four-week periods per year (not calendar months). This matches the Slice Society financial model format.

Weekly revenue × 4 weeks = period revenue, with ramp-up applied to periods 1-4.

Output: Full P&L with Revenue → Product Cost → Gross Margin → Wages → Operating Costs → Fixed Costs → EBITDA → Net Profit

#### 9. 5-Year Projections

- Revenue grows at `revenue_growth_pct` per year
- COGS stable at target %
- Labor efficiency improves slightly (management flat, hourly scales with revenue)
- Operating costs scale with revenue
- Fixed costs grow at 2-3% inflation

#### 10. Balance Sheet

- Assets: Cash, inventory, capital assets (depreciating over 5 years at ~10%/year)
- Liabilities: Loans (amortizing over 5 years), accounts payable
- Equity: Shareholder investment + retained earnings

### AI Narrative for Financial Model

Call GPT to generate methodology text for pages 2-4 (Introduction, Opening Budget methodology, Income Statement methodology). Pass the calculated numbers and let the model write explanatory paragraphs around them — similar to the Slice Society financial model's text sections.

### Financial PDF Template

Same white professional style as business plan PDF. Dense tables with:
- Period headers across top
- Category rows with % of revenue
- Subtotals bolded
- Dollar formatting with commas

---

## P3: Prompt Engineering & Market Intelligence

### New File: `orchestration/market_data.py`

Static dictionary of F&B benchmarks by country/city.

**Structure:**

```python
MARKET_DATA = {
    "lebanon": {
        "beirut": {
            "avg_rent_sqm_usd": {"low": 15, "mid": 30, "high": 60},
            "hourly_labor_rate_usd": {"low": 3, "mid": 5, "high": 8},
            "management_salary_range_usd": {"low": 18000, "high": 36000},
            "popular_local_ingredients": ["labneh", "za'atar", "sumac", "akkawi cheese", ...],
            "local_suppliers": ["general supplier context"],
            "dining_scene": "Beirut has a vibrant F&B scene with...",
            "licensing_notes": "...",
            "currency": "USD",
            "typical_cogs_pct": {"food": 28, "beverage": 25},
            "population_context": "...",
        }
    },
    "canada": {
        "ottawa": { ... }
    },
    "uae": {
        "dubai": { ... }
    },
    "saudi_arabia": {
        "riyadh": { ... }
    }
}
```

**Fallback:** If city/country not in the dictionary, the prompt omits market data and the AI generates based on its own knowledge. No hard failure.

### Prompt Injection Point

In `section_bundle_generator.py`, add a `MARKET_CONTEXT` block before the concept JSON:

```
MARKET CONTEXT for {city}, {country}:
- Typical rent range: ${low}-${high} per sqm/month
- Labor rates: ${hourly_low}-${hourly_high}/hour
- Popular local ingredients: {list}
- Dining scene: {description}
- Population context: {description}

Use this data to make content specific and locally relevant.
```

### Prompt Overhaul: Section-Specific Instructions

Add a `prompt_hint` field to each section spec in `section_specs.py`:

```python
{"order": 4, "id": "concept_overview", ...,
 "prompt_hint": "Write 2+ paragraphs. Weave in the founder's background naturally. Reference the local market opportunity. Explain what makes this concept different from existing options in the area."}
```

These hints are appended to the section specs sent to the model, giving per-section writing guidance without bloating the system prompt.

### Owner Story Weaving

Add to system prompt:

```
FOUNDER INTEGRATION:
The founder's background is: {founder_background}
Naturally reference the founder's relevant experience in these sections:
concept_overview, food_program, location_strategy, our_guests, ownership_profile.
Do NOT confine the founder story to just the ownership section.
Write as if the consultant has interviewed the founder and is presenting their vision.
```

### Confidence-Aware Tone

Add to system prompt:

```
CONFIDENCE-AWARE WRITING:
- When a value has confidence="user_provided", state it as decided fact: "The restaurant will operate 6 days per week."
- When confidence="ai_assumed", frame as recommendation: "Based on market analysis for {city}, we recommend targeting approximately X orders per day."
- When confidence="user_unknown", acknowledge the gap: "This will be determined based on the final location selection."
```

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `templates/plan_pdf.html` | NEW — print-optimized PDF template |
| `templates/_blocks_pdf.html` | NEW — print block macros |
| `templates/financial_pdf.html` | NEW — financial model PDF template |
| `templates/_blocks.html` | ADD menu_items block type |
| `templates/wizard.html` | ADD new financial anchor fields |
| `orchestration/section_specs.py` | UPDATE max_words, ADD prompt_hint fields |
| `orchestration/section_bundle_generator.py` | UPDATE prompts, max_tokens, chunk_size |
| `orchestration/financial_model_generator.py` | NEW — full financial model engine |
| `orchestration/market_data.py` | NEW — regional market benchmarks |
| `orchestration/schemas.py` | ADD MenuItemsBlock to block union |
| `app.py` | ADD financial-pdf route, UPDATE pdf route to use new template |

---

## Out of Scope

- Multi-language support (stays English-only for now)
- RAG system for real-time market data (static dictionary is sufficient for MVP)
- Custom branding per client (logo upload, color picker) — future enhancement
- Interactive financial model (editable spreadsheet) — future enhancement
