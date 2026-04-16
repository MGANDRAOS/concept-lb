# Production PDF Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the AI-generated business plan from a dark-mode web preview into a professional, consultant-grade PDF matching the quality of a $40K hospitality consultancy deliverable, with deeper content, a separate financial model PDF, and region-aware prompts.

**Architecture:** Four sequential priorities — P0 builds the print PDF template, P1 deepens content and adds a menu_items block type, P2 adds a full financial model generator with separate PDF export, P3 enriches prompts with market data and per-section writing hints. Each priority builds on the previous.

**Tech Stack:** Flask, Jinja2, Playwright (headless Chromium PDF), OpenAI GPT-5.2, Pydantic, SQLite

**Spec:** `docs/superpowers/specs/2026-04-16-production-pdf-enhancement-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `templates/plan_pdf.html` | Print-optimized PDF template (white theme, A4, sidebar, page numbers) |
| `templates/_blocks_pdf.html` | Jinja2 macros for rendering blocks in print PDF context |
| `templates/financial_pdf.html` | Financial model PDF template (tables, P&L, balance sheet) |
| `orchestration/financial_model_generator.py` | Deterministic financial calculations + AI narrative |
| `orchestration/market_data.py` | Static F&B benchmarks by country/city |

### Modified Files
| File | What Changes |
|------|-------------|
| `schemas/plan_schema.py` | Add `MenuItem`, `MenuItemsBlock` models; update `Block` union |
| `orchestration/section_specs.py` | Increase `max_words`, add `prompt_hint` fields |
| `orchestration/section_bundle_generator.py` | New prompt sections, increase `max_tokens`, reduce `chunk_size` |
| `templates/_blocks.html` | Add `menu_items` block rendering for web view |
| `templates/wizard.html` | Add new financial anchor fields for P2 |
| `schemas/concept_schema.py` | Add new financial anchor fields to ConceptObject |
| `app.py` | Update PDF export route, add financial PDF route |

---

## Task 1: Add MenuItemsBlock to Pydantic schemas

**Files:**
- Modify: `schemas/plan_schema.py:5-37`

- [ ] **Step 1: Add MenuItem and MenuItemsBlock models**

Open `schemas/plan_schema.py`. After the existing `ImageBlock` class (line 34) and before the `Block` union (line 37), add:

```python
class MenuItem(BaseModel):
    name: str
    description: str

class MenuItemsBlock(BaseModel):
    type: Literal["menu_items"]
    category: str
    items: List[MenuItem]
```

- [ ] **Step 2: Update BlockType literal and Block union**

Change line 5 from:
```python
BlockType = Literal["paragraph", "bullets", "table", "callout", "image"]
```
to:
```python
BlockType = Literal["paragraph", "bullets", "table", "callout", "image", "menu_items"]
```

Change line 37 from:
```python
Block = Union[ParagraphBlock, BulletsBlock, TableBlock, CalloutBlock, ImageBlock]
```
to:
```python
Block = Union[ParagraphBlock, BulletsBlock, TableBlock, CalloutBlock, ImageBlock, MenuItemsBlock]
```

- [ ] **Step 3: Verify schema loads without errors**

Run: `cd /c/Users/User/Documents/concept-lb/.claude/worktrees/upbeat-wing && python -c "from schemas.plan_schema import Block, MenuItemsBlock, MenuItem; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add schemas/plan_schema.py
git commit -m "feat: add MenuItemsBlock schema for full dish menu rendering"
```

---

## Task 2: Add menu_items block rendering to web template

**Files:**
- Modify: `templates/_blocks.html`

- [ ] **Step 1: Add menu_items block rendering**

In `templates/_blocks.html`, before the `else` fallback block (line 61), add a new `elif` block:

```jinja2
{% elif block.get("type") == "menu_items" %}
  <div class="menu-category">
    {% if block.get("category") %}
      <h3 style="text-transform:uppercase; font-size:14px; letter-spacing:1px; margin:16px 0 10px; color:var(--accent);">{{ block.get("category") }}</h3>
    {% endif %}
    {% for item in block.get("items", []) %}
      <div style="margin:8px 0;">
        <strong style="text-transform:uppercase;">{{ item.get("name", "") }}</strong><br>
        <span style="color:var(--muted); font-size:13px;">{{ item.get("description", "") }}</span>
      </div>
    {% endfor %}
  </div>
```

- [ ] **Step 2: Verify template syntax**

Run: `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); t = env.get_template('_blocks.html'); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add templates/_blocks.html
git commit -m "feat: add menu_items block rendering to web template"
```

---

## Task 3: Create print-optimized PDF block macros

**Files:**
- Create: `templates/_blocks_pdf.html`

- [ ] **Step 1: Create the file**

Create `templates/_blocks_pdf.html` with all block types styled for white-background print:

```jinja2
{# templates/_blocks_pdf.html — print-optimized block rendering #}
{% macro render_block(block) %}

{% if block.get("type") == "paragraph" %}
  <p>{{ block.get("text", "") }}</p>

{% elif block.get("type") == "bullets" %}
  <ul>
    {% for item in block.get("items", []) %}
      <li>{{ item }}</li>
    {% endfor %}
  </ul>

{% elif block.get("type") == "callout" %}
  <div class="callout">
    {% if block.get("title") %}
      <div class="callout-title">{{ block.get("title") }}</div>
    {% endif %}
    <div>{{ block.get("text", "") }}</div>
  </div>

{% elif block.get("type") == "image" %}
  <figure class="plan-image">
    <img src="{{ block.get('src', '') }}" alt="{{ block.get('alt', '') }}" />
    {% if block.get("caption") %}
      <figcaption>{{ block.get("caption") }}</figcaption>
    {% endif %}
  </figure>

{% elif block.get("type") == "table" %}
  <div class="table-wrap">
    <table>
      {% if block.get("columns") %}
      <thead>
        <tr>
          {% for col in block.get("columns", []) %}
            <th>{{ col }}</th>
          {% endfor %}
        </tr>
      </thead>
      {% endif %}
      <tbody>
        {% for row in block.get("rows", []) %}
          <tr class="{{ 'alt-row' if loop.index is odd else '' }}">
            {% for cell in row %}
              <td>{{ cell }}</td>
            {% endfor %}
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

{% elif block.get("type") == "menu_items" %}
  <div class="menu-category">
    {% if block.get("category") %}
      <h3 class="menu-category-title">{{ block.get("category") }}</h3>
    {% endif %}
    <div class="menu-items-grid">
      {% for item in block.get("items", []) %}
        <div class="menu-item">
          <span class="dish-name">{{ item.get("name", "") }}</span>
          <span class="dish-desc">{{ item.get("description", "") }}</span>
        </div>
      {% endfor %}
    </div>
  </div>

{% else %}
  <pre class="unknown">{{ block }}</pre>
{% endif %}

{% endmacro %}
```

- [ ] **Step 2: Verify template syntax**

Run: `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); t = env.get_template('_blocks_pdf.html'); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add templates/_blocks_pdf.html
git commit -m "feat: add print-optimized block macros for PDF export"
```

---

## Task 4: Create the professional PDF template

**Files:**
- Create: `templates/plan_pdf.html`

- [ ] **Step 1: Create the full PDF template**

Create `templates/plan_pdf.html`. This is the core P0 deliverable — a professional white-background A4 template matching the Slice Society style:

```html
{# templates/plan_pdf.html — Professional print-optimized PDF #}
<!doctype html>
<html lang="{{ plan.plan_meta.language or 'en' }}">
<head>
  <meta charset="utf-8" />
  <title>{{ plan.plan_meta.concept_name or "Business Plan" }}</title>
  <style>
    /* ── Reset & Base ────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    @page {
      size: A4;
      margin: 25mm 22mm 28mm 22mm;
    }

    body {
      background: #fff;
      color: #1a1a1a;
      font: 11pt/1.65 'Segoe UI', Helvetica, Arial, sans-serif;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }

    /* ── Sidebar Brand (repeats every page) ──────────── */
    .sidebar-brand {
      position: fixed;
      right: -14mm;
      top: 50%;
      transform: rotate(90deg) translateX(-50%);
      font-size: 8pt;
      color: #d0d0d0;
      letter-spacing: 3px;
      text-transform: uppercase;
      font-family: Georgia, 'Times New Roman', serif;
      white-space: nowrap;
    }

    /* ── Page Number (fixed footer) ──────────────────── */
    .page-number {
      position: fixed;
      bottom: -18mm;
      left: 0;
      right: 0;
      text-align: center;
      font-size: 9pt;
      color: #999;
    }

    /* ── Cover Page ──────────────────────────────────── */
    .cover {
      page-break-after: always;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      text-align: center;
      padding: 60mm 20mm;
    }

    .cover-accent {
      width: 60px;
      height: 4px;
      background: #2c5282;
      margin: 0 auto 30px;
    }

    .cover h1 {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 32pt;
      font-weight: 700;
      color: #1a1a1a;
      margin-bottom: 12px;
      letter-spacing: -0.5px;
    }

    .cover .subtitle {
      font-size: 14pt;
      color: #555;
      font-weight: 300;
      margin-bottom: 40px;
    }

    .cover .date {
      font-size: 11pt;
      color: #888;
    }

    /* ── Table of Contents ───────────────────────────── */
    .toc {
      page-break-after: always;
      padding-top: 20mm;
    }

    .toc h2 {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 18pt;
      margin-bottom: 20px;
      color: #1a1a1a;
    }

    .toc-entry {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 6px 0;
      border-bottom: 1px dotted #ddd;
      font-size: 11pt;
    }

    .toc-entry .toc-title {
      color: #1a1a1a;
    }

    .toc-entry .toc-page {
      color: #888;
      font-size: 10pt;
      min-width: 30px;
      text-align: right;
    }

    /* ── Section ─────────────────────────────────────── */
    .section {
      page-break-before: always;
    }

    .section h2 {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 18pt;
      color: #1a1a1a;
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 2px solid #2c5282;
    }

    /* ── Typography ──────────────────────────────────── */
    p {
      margin: 10px 0;
      text-align: justify;
      orphans: 3;
      widows: 3;
    }

    ul {
      margin: 10px 0 10px 22px;
    }

    li {
      margin: 5px 0;
    }

    h3 {
      font-size: 12pt;
      font-weight: 700;
      margin: 18px 0 8px;
      color: #2c5282;
    }

    /* ── Callout ─────────────────────────────────────── */
    .callout {
      background: #f7fafc;
      border-left: 3px solid #2c5282;
      padding: 12px 16px;
      margin: 14px 0;
      font-size: 10.5pt;
    }

    .callout-title {
      font-weight: 700;
      margin-bottom: 4px;
    }

    /* ── Tables ──────────────────────────────────────── */
    .table-wrap {
      margin: 14px 0;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10pt;
    }

    th, td {
      padding: 8px 10px;
      border: 1px solid #ddd;
      vertical-align: top;
      text-align: left;
    }

    th {
      background: #f5f5f5;
      font-weight: 700;
      color: #333;
    }

    tr.alt-row {
      background: #fafafa;
    }

    /* ── Images ──────────────────────────────────────── */
    .plan-image {
      margin: 16px 0;
      text-align: center;
    }

    .plan-image img {
      max-width: 100%;
      height: auto;
    }

    .plan-image figcaption {
      font-size: 9pt;
      color: #888;
      margin-top: 6px;
      font-style: italic;
    }

    /* ── Menu Items ──────────────────────────────────── */
    .menu-category-title {
      text-transform: uppercase;
      font-size: 11pt;
      letter-spacing: 1.5px;
      color: #2c5282;
      margin: 20px 0 10px;
      font-family: Georgia, 'Times New Roman', serif;
    }

    .menu-items-grid {
      columns: 2;
      column-gap: 24px;
    }

    .menu-item {
      break-inside: avoid;
      margin-bottom: 10px;
    }

    .dish-name {
      display: block;
      font-weight: 700;
      text-transform: uppercase;
      font-size: 10pt;
      letter-spacing: 0.5px;
    }

    .dish-desc {
      display: block;
      font-size: 9.5pt;
      color: #555;
    }

    /* ── Closing Page ────────────────────────────────── */
    .closing {
      page-break-before: always;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      min-height: 80vh;
      text-align: center;
    }

    .closing h2 {
      border-bottom: none;
      font-size: 22pt;
    }

    /* ── Utility ─────────────────────────────────────── */
    .unknown {
      background: #fff3f3;
      border: 1px solid #fcc;
      padding: 8px;
      font-size: 9pt;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>
  {% from "_blocks_pdf.html" import render_block %}

  <!-- Sidebar brand (repeats on every printed page) -->
  <div class="sidebar-brand">{{ plan.plan_meta.concept_name or "" }}</div>

  <!-- ── Cover Page ────────────────────────────────── -->
  <div class="cover">
    <div class="cover-accent"></div>
    <h1>{{ plan.plan_meta.concept_name or "Restaurant Concept" }}</h1>
    <div class="subtitle">Business Plan</div>
    <div class="date">{{ plan.plan_meta.created_at[:10] if plan.plan_meta.created_at else "" }}</div>
  </div>

  <!-- ── Table of Contents ─────────────────────────── -->
  <div class="toc">
    <h2>Contents</h2>
    {% for section in (plan.sections or []) %}
      {% if section.id != "cover_page" %}
        <div class="toc-entry">
          <span class="toc-title">{{ section.title }}</span>
          <span class="toc-page">{{ loop.index + 1 }}</span>
        </div>
      {% endif %}
    {% endfor %}
  </div>

  <!-- ── Sections ──────────────────────────────────── -->
  {% for section in (plan.sections or []) %}
    {% if section.id == "closing_page" %}
      <div class="closing">
        <h2>Thank You.</h2>
        <p style="margin-top:12px; color:#888;">Business Plan &mdash; {{ plan.plan_meta.concept_name or "" }}</p>
      </div>
    {% elif section.id != "cover_page" %}
      <div class="section" id="{{ section.id }}">
        <h2>{{ section.title }}</h2>
        {% for block in (section.blocks or []) %}
          {{ render_block(block) }}
        {% endfor %}
      </div>
    {% endif %}
  {% endfor %}

</body>
</html>
```

- [ ] **Step 2: Verify template syntax**

Run: `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); t = env.get_template('plan_pdf.html'); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add templates/plan_pdf.html
git commit -m "feat: add professional white-theme PDF template with cover, TOC, sidebar branding"
```

---

## Task 5: Update PDF export route in app.py

**Files:**
- Modify: `app.py:529-576`

- [ ] **Step 1: Update the PDF export function to use the new template**

Replace the existing `plan_export_pdf` function (lines 529-576) with a version that renders `plan_pdf.html` from the plan JSON instead of using cached `plan_html`:

Find the existing route function that starts with `@app.route("/plans/<plan_id>/export/pdf")` and replace its body. The key changes:

1. Load plan JSON from database instead of cached HTML
2. Render `plan_pdf.html` template with the plan data
3. Use Playwright's `headerTemplate`/`footerTemplate` for page numbers (more reliable than CSS counters in Chromium)
4. Set `displayHeaderFooter=True`

```python
@app.route("/plans/<plan_id>/export/pdf")
def plan_export_pdf(plan_id):
    plan_record = _get_plan_or_404(plan_id)
    if not plan_record:
        return "Plan not found", 404

    # Parse plan JSON to render with the PDF template
    import json as _json
    plan_json = plan_record.get("plan_json")
    if not plan_json:
        return "Plan data not available for PDF export", 400

    plan_data = _json.loads(plan_json) if isinstance(plan_json, str) else plan_json

    # Render the print-optimized PDF template
    html = render_template("plan_pdf.html", plan=_wrap_plan(plan_data))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded", timeout=60_000)

        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template='<div style="width:100%;text-align:center;font-size:9px;color:#999;"><span class="pageNumber"></span></div>',
            margin={
                "top": "25mm",
                "bottom": "28mm",
                "left": "22mm",
                "right": "22mm",
            },
        )
        browser.close()

    safe_name = "".join(c for c in (plan_data.get("plan_meta", {}).get("concept_name", "") or "plan") if c.isalnum() or c in " _-").strip() or "plan"
    filename = f"ConceptLB_{safe_name}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
```

Note: You'll need a helper `_wrap_plan` that converts the plan dict into an object with attribute access for Jinja2 dot notation. Check if the existing code already has one — if it uses a class like `DotDict` or `SimpleNamespace`, reuse it. If not, add a simple recursive wrapper:

```python
class _DotDict:
    def __init__(self, d):
        for k, v in (d or {}).items():
            if isinstance(v, dict):
                setattr(self, k, _DotDict(v))
            elif isinstance(v, list):
                setattr(self, k, [_DotDict(i) if isinstance(i, dict) else i for i in v])
            else:
                setattr(self, k, v)

def _wrap_plan(plan_data):
    return _DotDict(plan_data)
```

Check how the existing `plan_view.html` template accesses `plan` — if it already uses dict access (`plan["sections"]`) rather than attribute access (`plan.sections`), then you don't need the wrapper. Match the existing pattern.

- [ ] **Step 2: Test PDF export manually**

Start the Flask server and generate a plan through the wizard, then hit the PDF export route. Verify:
- Cover page renders with concept name, "Business Plan", and date
- Table of contents is present on page 2
- Each section starts on a new page
- White background, dark text
- Sidebar brand name visible on pages
- Page numbers appear in footer

Run: `python app.py` then visit `http://localhost:5000/plans/<latest_plan_id>/export/pdf`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: update PDF export to use professional print template with page numbers"
```

---

## Task 6: Update section specs — increase word budgets and add prompt hints

**Files:**
- Modify: `orchestration/section_specs.py`

- [ ] **Step 1: Update max_words and add prompt_hint for each section**

Replace the entire `SECTION_SPECS` list in `orchestration/section_specs.py` with the updated version. Changes: increased `max_words` for 15 sections, added `prompt_hint` field to all sections for P3 per-section writing guidance:

```python
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
```

- [ ] **Step 2: Verify specs load**

Run: `python -c "from orchestration.section_specs import SECTION_SPECS; print(f'{len(SECTION_SPECS)} sections loaded'); assert all('prompt_hint' in s for s in SECTION_SPECS), 'missing prompt_hint'"`
Expected: `30 sections loaded` with no assertion error

- [ ] **Step 3: Commit**

```bash
git add orchestration/section_specs.py
git commit -m "feat: increase word budgets and add per-section prompt hints"
```

---

## Task 7: Update section_bundle_generator.py — new prompts and token limits

**Files:**
- Modify: `orchestration/section_bundle_generator.py`

- [ ] **Step 1: Update the system prompt**

In `orchestration/section_bundle_generator.py`, replace the `BUNDLE_SYSTEM_PROMPT` string (lines 9-56) with an expanded version. Add after the existing CONTENT RULES section:

```python
BUNDLE_SYSTEM_PROMPT = """You are Concept LB, a senior hospitality consultant presenting a restaurant concept to investors.

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
        { "type": "table", "columns": ["..."], "rows": [["..."]] },
        { "type": "menu_items", "category": "...", "items": [{"name": "DISH NAME", "description": "Ingredient, Ingredient, Sauce"}] }
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
  - Do NOT mention AI, prompts, or that this was generated.
- Keep content consultant-grade, specific, and actionable.
- Avoid generic statements. Be specific to this concept, this city, this cuisine.
- If concept.derived_financials.outputs is present:
  - Use those numbers exactly for any revenue/margin/breakeven mentions.
  - Do NOT invent or recompute alternative totals.
  - If an output is null, state it cannot be computed yet due to missing inputs.

MENU SECTION RULES (for sections with menu_items in required_blocks):
- Generate a complete menu with specific dishes.
- Each dish MUST have: a creative name appropriate to the cuisine, and a comma-separated ingredient list.
- Use the "menu_items" block type with "category" and "items" array.
- Each item has "name" (uppercase string) and "description" (ingredients string).
- Generate 8-15 dishes per meal period.
- Dishes must reflect the cuisine type and incorporate local ingredients.
- Name specific cheeses, herbs, proteins, sauces, and produce — not generic terms.
- Include at least one "WEEKLY SPECIAL" placeholder per category with description "Created by Our Team to Highlight Amazing Seasonal Ingredients".

FOUNDER INTEGRATION:
- Naturally reference the founder's relevant experience in concept_overview, food_program, location_strategy, our_guests, and ownership_profile sections.
- Write as if you (the consultant) have interviewed the founder and are presenting their vision.

CONFIDENCE-AWARE WRITING:
- When a financial anchor has confidence="user_provided", state it as decided fact.
- When confidence="ai_assumed", frame as recommendation: "Based on market analysis, we recommend..."
- When confidence="user_unknown", acknowledge: "This will be determined based on..."

SECTION-SPECIFIC HINTS:
Each section spec includes a "prompt_hint" field. Follow its guidance for that section's content, depth, and structure.
"""
```

- [ ] **Step 2: Update token limits and chunk size**

Find the `max_output_tokens` default parameter (line 93) and change from `3200` to `8000`:

```python
max_output_tokens: int = 8000
```

Find the fallback token increase (line 196) and change from `max(max_output_tokens, 4000)` to `max(max_output_tokens, 10000)`:

```python
max_output_tokens=max(max_output_tokens, 10000),
```

In `app.py`, find where `chunk_size` defaults to 6 (line 104) and change to 4:

```python
chunk_size = int(request.args.get("chunk_size", 4))
```

Also in `app.py`, find the `max_output_tokens` values for `generate_section_bundles` calls and update:
- Normal: `3200` → `8000`
- With assumptions: `4200` → `10000`

- [ ] **Step 3: Add prompt_hint to the specs sent to the model**

In the section where `specs_json` is built (the code that serializes section specs for the user prompt), ensure `prompt_hint` is included in each spec dict sent to the model. Check if the existing code filters spec fields — if so, add `prompt_hint` to the allowed fields.

- [ ] **Step 4: Add market context injection**

In the function that builds the user prompt (near the financial anchors summary block, lines 110-139), add a market context block. After the anchors summary and before the concept JSON:

```python
# Market context injection
from orchestration.market_data import get_market_context
market_ctx = get_market_context(
    concept.get("country", ""),
    concept.get("city", "")
)
if market_ctx:
    parts.append(f"\nMARKET CONTEXT for {concept.get('city', '')}, {concept.get('country', '')}:\n{market_ctx}\n\nUse this data to make content specific and locally relevant.\n")
```

This depends on Task 9 (market_data.py) being complete. If implementing in order, add the import and call but it will be a no-op until the market_data module exists.

- [ ] **Step 5: Add required_blocks validation for menu_items**

In the validation section (lines 217-276), ensure `menu_items` is recognized as a valid block type. The existing validation checks that each section's blocks contain the required block types — `menu_items` should now be accepted.

- [ ] **Step 6: Commit**

```bash
git add orchestration/section_bundle_generator.py app.py
git commit -m "feat: expand prompts with menu rules, founder integration, confidence tone, and increase token limits"
```

---

## Task 8: Add new financial fields to ConceptObject schema and wizard

**Files:**
- Modify: `schemas/concept_schema.py`
- Modify: `templates/wizard.html`

- [ ] **Step 1: Add new fields to ConceptObject**

In `schemas/concept_schema.py`, add the following optional fields to the `ConceptObject` class (after the existing financial anchors around line 70):

```python
    # P2: Financial model anchors
    opening_budget_usd: Optional[float] = None
    funding_equity_pct: Optional[float] = Field(default=50, ge=0, le=100)
    funding_loan_pct: Optional[float] = Field(default=50, ge=0, le=100)
    avg_check_morning: Optional[float] = None
    avg_check_daytime: Optional[float] = None
    avg_check_evening: Optional[float] = None
    revenue_growth_pct: Optional[float] = Field(default=3, ge=0, le=20)
    ramp_up_months: Optional[int] = Field(default=4, ge=1, le=12)
    ramp_start_pct: Optional[float] = Field(default=60, ge=10, le=100)
```

- [ ] **Step 2: Add new fields to wizard Step 5**

In `templates/wizard.html`, in the Step 5 (Financial Anchors) section, add the new input fields. Find the existing financial anchor inputs and add after them:

```javascript
// In the data model defaults (around line 45-80 in the script section):
opening_budget_usd: null,
funding_equity_pct: 50,
funding_loan_pct: 50,
avg_check_morning: null,
avg_check_daytime: null,
avg_check_evening: null,
revenue_growth_pct: 3,
ramp_up_months: 4,
ramp_start_pct: 60,
```

Add the HTML form fields in the Step 5 render function. Group them under a "Financial Model Inputs" subheading:

```html
<h3 style="margin-top:24px; color:var(--accent);">Financial Model Inputs (Optional)</h3>
<p style="color:var(--muted); font-size:13px; margin-bottom:12px;">These fields are used to generate the separate Financial Model PDF. Leave blank for industry defaults.</p>
```

Then add `inputNumber` calls for each field with appropriate labels, min/max, and placeholders.

- [ ] **Step 3: Add confidence tracking for new fields**

In the wizard's confidence source dropdowns, add source tracking for `opening_budget_usd` and `avg_check_*` fields following the existing pattern (e.g., `opening_budget_usd__source: "user_unknown"`).

- [ ] **Step 4: Commit**

```bash
git add schemas/concept_schema.py templates/wizard.html
git commit -m "feat: add financial model fields to schema and wizard"
```

---

## Task 9: Create market_data.py

**Files:**
- Create: `orchestration/market_data.py`

- [ ] **Step 1: Create the market data module**

```python
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
```

- [ ] **Step 2: Test the module**

Run: `python -c "from orchestration.market_data import get_market_context; ctx = get_market_context('Lebanon', 'Beirut'); print(ctx[:200] if ctx else 'None')"`
Expected: Output starting with `- Typical rent range: $15-$55 per sqm/month`

Run: `python -c "from orchestration.market_data import get_market_context; ctx = get_market_context('Unknown Country', 'Unknown'); print(ctx)"`
Expected: `None`

- [ ] **Step 3: Commit**

```bash
git add orchestration/market_data.py
git commit -m "feat: add regional F&B market data for Lebanon, Canada, UAE, Saudi Arabia"
```

---

## Task 10: Create the financial model generator

**Files:**
- Create: `orchestration/financial_model_generator.py`

- [ ] **Step 1: Create the financial model calculation engine**

This is the largest new file. It performs all deterministic financial calculations and calls AI only for methodology narrative text.

```python
"""
orchestration/financial_model_generator.py
Generates a complete financial model from concept data.
All numbers are deterministic. AI is only used for narrative methodology text.
"""

import math
from typing import Dict, List, Optional, Any
from orchestration.llm_client import call_model_json


# ── Budget allocation defaults by concept type ──────────────
BUDGET_ALLOCATION = {
    "dine_in": {
        "building": 0.33, "equipment": 0.36, "operating_supplies": 0.07,
        "preopening": 0.11, "marketing": 0.02, "working_capital": 0.06,
        "misc_financing": 0.06,
    },
    "qsr": {
        "building": 0.25, "equipment": 0.40, "operating_supplies": 0.08,
        "preopening": 0.10, "marketing": 0.03, "working_capital": 0.07,
        "misc_financing": 0.07,
    },
    "hybrid": {
        "building": 0.30, "equipment": 0.37, "operating_supplies": 0.07,
        "preopening": 0.10, "marketing": 0.02, "working_capital": 0.07,
        "misc_financing": 0.07,
    },
}

# ── COGS by product category ────────────────────────────────
DEFAULT_COGS_PCT = {
    "food": 27.0,
    "minerals": 30.0,
    "liquor": 22.0,
    "wine": 32.0,
    "beer": 32.0,
}

# ── Revenue split defaults ──────────────────────────────────
REVENUE_SPLIT_ALCOHOL = {
    "food": 0.76, "minerals": 0.12, "liquor": 0.04, "wine": 0.04, "beer": 0.04,
}
REVENUE_SPLIT_NO_ALCOHOL = {
    "food": 0.85, "minerals": 0.15, "liquor": 0.0, "wine": 0.0, "beer": 0.0,
}

# ── Management salary by staff model and country tier ───────
MGMT_SALARY = {
    "lean":     {"high": 75000, "mid": 45000, "low": 24000},
    "standard": {"high": 150000, "mid": 90000, "low": 48000},
    "full":     {"high": 225000, "mid": 135000, "low": 72000},
}

# Country to salary tier mapping
COUNTRY_SALARY_TIER = {
    "lebanon": "low", "canada": "high", "united states": "high",
    "uae": "mid", "saudi arabia": "mid", "qatar": "mid",
    "kuwait": "mid", "bahrain": "mid", "egypt": "low",
    "jordan": "low", "iraq": "low",
}

# ── Weekly cover distribution (Mon-Sun pattern) ─────────────
WEEKLY_PATTERN = [0.11, 0.12, 0.14, 0.15, 0.18, 0.17, 0.13]  # Mon-Sun

# ── Meal period time allocation ─────────────────────────────
MEAL_PERIOD_SPLIT = {
    "morning":    0.20,
    "brunch":     0.15,
    "lunch":      0.30,
    "dinner":     0.40,
    "late_night": 0.10,
}


def _get_salary_tier(country: str) -> str:
    return COUNTRY_SALARY_TIER.get(country.lower().strip(), "mid")


def generate_financial_model(concept: Dict, derived_financials: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Generate a complete financial model from concept data.
    Returns a dict with all financial model sections ready for template rendering.
    """
    outputs = (derived_financials or {}).get("outputs", {}) or {}
    confidence = concept.get("confidence", {})

    service_model = concept.get("service_model", "hybrid")
    has_alcohol = concept.get("alcohol_flag", False)
    country = concept.get("country", "Lebanon")
    salary_tier = _get_salary_tier(country)
    staff_model = concept.get("staff_model", "lean")
    meal_periods = concept.get("meal_periods", ["lunch", "dinner"])

    # ── 1. Opening Budget ────────────────────────────────────
    opening_budget = concept.get("opening_budget_usd") or concept.get("capex_budget_usd")
    budget_breakdown = None
    if opening_budget and opening_budget > 0:
        alloc = BUDGET_ALLOCATION.get(service_model, BUDGET_ALLOCATION["hybrid"])
        budget_breakdown = {k: round(opening_budget * v) for k, v in alloc.items()}
        budget_breakdown["total"] = int(opening_budget)

    # ── 2. Funding Structure ─────────────────────────────────
    equity_pct = concept.get("funding_equity_pct", 50) or 50
    loan_pct = concept.get("funding_loan_pct", 50) or 50
    funding = None
    if opening_budget and opening_budget > 0:
        funding = {
            "equity": round(opening_budget * (equity_pct / 100)),
            "loan": round(opening_budget * (loan_pct / 100)),
            "total": int(opening_budget),
        }

    # ── 3. Average Checks ───────────────────────────────────
    avg_ticket = concept.get("avg_ticket_usd") or 15
    avg_check = {
        "morning": concept.get("avg_check_morning") or round(avg_ticket * 0.6, 2),
        "daytime": concept.get("avg_check_daytime") or round(avg_ticket * 0.9, 2),
        "evening": concept.get("avg_check_evening") or round(avg_ticket * 1.5, 2),
    }

    # ── 4. Weekly Covers & Sales ─────────────────────────────
    daily_orders = concept.get("expected_daily_orders") or 100
    op_days = concept.get("operating_days_per_week") or 7

    # Distribute orders across the week
    weekly_covers_total = daily_orders * op_days
    weekly_covers_by_day = []
    for i in range(7):
        if i < op_days:
            weekly_covers_by_day.append(round(weekly_covers_total * WEEKLY_PATTERN[i]))
        else:
            weekly_covers_by_day.append(0)

    # Split covers by meal period
    active_periods = [p for p in meal_periods if p in MEAL_PERIOD_SPLIT]
    if not active_periods:
        active_periods = ["lunch", "dinner"]
    total_weight = sum(MEAL_PERIOD_SPLIT[p] for p in active_periods)

    covers_by_period = {}
    for period in active_periods:
        weight = MEAL_PERIOD_SPLIT[period] / total_weight
        covers_by_period[period] = [round(day * weight) for day in weekly_covers_by_day]

    # Calculate weekly sales by period
    check_map = {
        "morning": avg_check["morning"],
        "brunch": avg_check["morning"],
        "lunch": avg_check["daytime"],
        "dinner": avg_check["evening"],
        "late_night": avg_check["evening"],
    }

    sales_by_period = {}
    for period, covers in covers_by_period.items():
        check = check_map.get(period, avg_ticket)
        sales_by_period[period] = [round(c * check) for c in covers]

    weekly_sales_total = sum(sum(s) for s in sales_by_period.values())

    # ── 5. Revenue Split ─────────────────────────────────────
    rev_split = REVENUE_SPLIT_ALCOHOL if has_alcohol else REVENUE_SPLIT_NO_ALCOHOL
    annual_revenue_steady = weekly_sales_total * 52

    revenue_by_category = {
        cat: round(annual_revenue_steady * pct) for cat, pct in rev_split.items()
    }

    # ── 6. Ramp-Up Model ────────────────────────────────────
    ramp_months = concept.get("ramp_up_months") or 4
    ramp_start = (concept.get("ramp_start_pct") or 60) / 100
    growth_pct = (concept.get("revenue_growth_pct") or 3) / 100

    # 13 four-week periods for Year 1
    ramp_factors = []
    for period in range(13):
        if period < ramp_months:
            factor = ramp_start + (1.0 - ramp_start) * (period / ramp_months)
        else:
            factor = 1.0
        ramp_factors.append(round(factor, 3))

    period_revenue = [round(weekly_sales_total * 4 * f) for f in ramp_factors]
    year1_revenue = sum(period_revenue)

    # ── 7. COGS ─────────────────────────────────────────────
    target_food_cogs = concept.get("target_cogs_pct") or DEFAULT_COGS_PCT["food"]
    cogs_pct = {**DEFAULT_COGS_PCT, "food": target_food_cogs}

    # COGS ramp: 130% in period 1, normalizing by period ramp_months
    cogs_ramp_factors = []
    for period in range(13):
        if period < ramp_months:
            factor = 1.3 - 0.3 * (period / ramp_months)
        else:
            factor = 1.0
        cogs_ramp_factors.append(round(factor, 3))

    # Period-level COGS
    period_cogs = []
    for i, rev in enumerate(period_revenue):
        weighted_cogs_pct = sum(
            rev_split[cat] * cogs_pct.get(cat, 27) for cat in rev_split
        )
        cogs_val = round(rev * (weighted_cogs_pct / 100) * cogs_ramp_factors[i])
        period_cogs.append(cogs_val)

    year1_cogs = sum(period_cogs)

    # ── 8. Wages ────────────────────────────────────────────
    mgmt_salary = MGMT_SALARY.get(staff_model, MGMT_SALARY["lean"]).get(salary_tier, 45000)

    # Hourly labor as % of revenue
    foh_labor_pct = 0.11
    boh_labor_pct = 0.18
    benefits_pct = 0.07

    period_wages = []
    for rev in period_revenue:
        hourly = rev * (foh_labor_pct + boh_labor_pct)
        mgmt_period = mgmt_salary / 13
        benefits = (hourly + mgmt_period) * benefits_pct
        period_wages.append(round(hourly + mgmt_period + benefits))

    year1_wages = sum(period_wages)

    # ── 9. Operating Costs ──────────────────────────────────
    variable_op_pct = 0.054  # sum of all variable operating cost percentages
    fixed_monthly_ops = 1000  # telephone + waste + equipment rental

    period_operating = []
    for rev in period_revenue:
        variable = rev * variable_op_pct
        fixed = fixed_monthly_ops  # per period (4 weeks ~ 1 month)
        period_operating.append(round(variable + fixed))

    year1_operating = sum(period_operating)

    # ── 10. Fixed Costs ─────────────────────────────────────
    monthly_rent = concept.get("monthly_rent_usd") or 0
    monthly_insurance = max(500, round(year1_revenue / 12 * 0.015))
    monthly_utilities = round(year1_revenue / 12 * 0.02)

    period_fixed = round((monthly_rent + monthly_insurance + monthly_utilities))  # per period
    year1_fixed = period_fixed * 13

    # ── 11. Year 1 Income Statement ─────────────────────────
    period_gross_margin = [period_revenue[i] - period_cogs[i] for i in range(13)]
    period_ebitda = [
        period_gross_margin[i] - period_wages[i] - period_operating[i] - period_fixed
        for i in range(13)
    ]

    year1_gross_margin = year1_revenue - year1_cogs
    year1_ebitda = year1_gross_margin - year1_wages - year1_operating - year1_fixed

    # Depreciation (10% of capital assets per year)
    capital_assets = 0
    if budget_breakdown:
        capital_assets = budget_breakdown.get("building", 0) + budget_breakdown.get("equipment", 0) + budget_breakdown.get("preopening", 0)
    annual_depreciation = round(capital_assets * 0.10)

    year1_net_profit = year1_ebitda - annual_depreciation

    year1_income = {
        "periods": list(range(1, 14)),
        "weekly_sales": [round(weekly_sales_total * f) for f in ramp_factors],
        "revenue": period_revenue,
        "cogs": period_cogs,
        "gross_margin": period_gross_margin,
        "wages": period_wages,
        "operating": period_operating,
        "fixed": [period_fixed] * 13,
        "ebitda": period_ebitda,
        "totals": {
            "revenue": year1_revenue,
            "cogs": year1_cogs,
            "gross_margin": year1_gross_margin,
            "wages": year1_wages,
            "operating": year1_operating,
            "fixed": year1_fixed,
            "ebitda": year1_ebitda,
            "depreciation": annual_depreciation,
            "net_profit": year1_net_profit,
        }
    }

    # ── 12. 5-Year Projections ──────────────────────────────
    five_year = []
    for year in range(1, 6):
        if year == 1:
            rev = year1_revenue
            cogs = year1_cogs
            wages = year1_wages
            ops = year1_operating
            fixed = year1_fixed
        else:
            rev = round(five_year[-1]["revenue"] * (1 + growth_pct))
            weighted_cogs_pct = sum(rev_split[cat] * cogs_pct.get(cat, 27) for cat in rev_split)
            cogs = round(rev * weighted_cogs_pct / 100)
            wages = round(mgmt_salary + rev * (foh_labor_pct + boh_labor_pct) * (1 + benefits_pct))
            ops = round(rev * variable_op_pct + fixed_monthly_ops * 13)
            fixed = round(year1_fixed * (1.025 ** (year - 1)))  # 2.5% inflation

        gross = rev - cogs
        ebitda = gross - wages - ops - fixed
        net = ebitda - annual_depreciation

        five_year.append({
            "year": year,
            "revenue": rev,
            "cogs": cogs,
            "cogs_pct": round(cogs / rev * 100, 1) if rev else 0,
            "gross_margin": gross,
            "wages": wages,
            "wages_pct": round(wages / rev * 100, 1) if rev else 0,
            "operating": ops,
            "fixed": fixed,
            "ebitda": ebitda,
            "ebitda_pct": round(ebitda / rev * 100, 1) if rev else 0,
            "depreciation": annual_depreciation,
            "net_profit": net,
            "net_profit_pct": round(net / rev * 100, 1) if rev else 0,
        })

    # ── 13. Balance Sheet ───────────────────────────────────
    balance_sheets = []
    cumulative_profit = 0
    loan_amount = funding["loan"] if funding else 0
    equity_amount = funding["equity"] if funding else 0

    for year in range(6):  # Opening + 5 years
        if year == 0:
            cash = round((opening_budget or 0) * 0.02) if opening_budget else 0
            net_p = 0
        else:
            net_p = five_year[year - 1]["net_profit"]
            cumulative_profit += net_p
            cash = round(max(0, (balance_sheets[-1]["cash"] if balance_sheets else 0) + net_p))

        accumulated_dep = annual_depreciation * year
        remaining_loan = max(0, round(loan_amount - (loan_amount / 5 * year)))

        balance_sheets.append({
            "label": "Opening" if year == 0 else f"Year {year}",
            "cash": cash,
            "inventory": 18000 if opening_budget else 0,
            "capital_assets": capital_assets - accumulated_dep,
            "total_assets": cash + 18000 + (capital_assets - accumulated_dep) if opening_budget else 0,
            "loan": remaining_loan,
            "equity": equity_amount,
            "retained_earnings": cumulative_profit,
        })

    # ── 14. Revenue by category (for Year 1 and 5-year) ─────
    rev_by_category_y1 = {
        cat: round(year1_revenue * pct) for cat, pct in rev_split.items()
    }
    cogs_by_category_y1 = {
        cat: round(rev_by_category_y1[cat] * cogs_pct.get(cat, 27) / 100)
        for cat in rev_split
    }

    return {
        "opening_budget": budget_breakdown,
        "funding": funding,
        "avg_check": avg_check,
        "weekly_covers_by_day": weekly_covers_by_day,
        "covers_by_period": covers_by_period,
        "sales_by_period": sales_by_period,
        "weekly_sales_total": weekly_sales_total,
        "revenue_split": rev_split,
        "revenue_by_category_y1": rev_by_category_y1,
        "cogs_by_category_y1": cogs_by_category_y1,
        "cogs_pct": cogs_pct,
        "ramp_factors": ramp_factors,
        "year1_income": year1_income,
        "five_year": five_year,
        "balance_sheets": balance_sheets,
        "mgmt_salary": mgmt_salary,
        "annual_depreciation": annual_depreciation,
        "meta": {
            "service_model": service_model,
            "has_alcohol": has_alcohol,
            "country": country,
            "currency": concept.get("currency", "USD"),
            "staff_model": staff_model,
            "meal_periods": meal_periods,
            "revenue_growth_pct": growth_pct * 100,
            "ramp_months": ramp_months,
        }
    }
```

- [ ] **Step 2: Test the calculations**

Run:
```bash
python -c "
from orchestration.financial_model_generator import generate_financial_model
result = generate_financial_model({
    'concept_name': 'Test Cafe',
    'service_model': 'hybrid',
    'alcohol_flag': True,
    'country': 'Lebanon',
    'expected_daily_orders': 120,
    'avg_ticket_usd': 18,
    'operating_days_per_week': 7,
    'monthly_rent_usd': 3000,
    'opening_budget_usd': 200000,
    'staff_model': 'standard',
    'meal_periods': ['lunch', 'dinner'],
})
print(f'Year 1 revenue: \${result[\"year1_income\"][\"totals\"][\"revenue\"]:,}')
print(f'Year 1 net profit: \${result[\"year1_income\"][\"totals\"][\"net_profit\"]:,}')
print(f'5-year revenue: {[\"\${:,}\".format(y[\"revenue\"]) for y in result[\"five_year\"]]}')
print(f'Opening budget total: \${result[\"opening_budget\"][\"total\"]:,}')
"
```
Expected: Reasonable financial numbers — Year 1 revenue in the hundreds of thousands, 5-year shows growth.

- [ ] **Step 3: Commit**

```bash
git add orchestration/financial_model_generator.py
git commit -m "feat: add deterministic financial model generator with 5-year projections"
```

---

## Task 11: Create the financial model PDF template

**Files:**
- Create: `templates/financial_pdf.html`

- [ ] **Step 1: Create the financial PDF template**

```html
{# templates/financial_pdf.html — Financial Model PDF #}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ concept_name or "Financial Model" }}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    @page {
      size: A4 landscape;
      margin: 18mm 15mm 22mm 15mm;
    }

    body {
      background: #fff;
      color: #1a1a1a;
      font: 9.5pt/1.5 'Segoe UI', Helvetica, Arial, sans-serif;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }

    .sidebar-brand {
      position: fixed;
      right: -10mm;
      top: 50%;
      transform: rotate(90deg) translateX(-50%);
      font-size: 7pt;
      color: #d0d0d0;
      letter-spacing: 3px;
      text-transform: uppercase;
      font-family: Georgia, 'Times New Roman', serif;
    }

    /* Cover */
    .cover {
      page-break-after: always;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      text-align: center;
    }

    .cover-accent { width: 60px; height: 4px; background: #2c5282; margin: 0 auto 30px; }
    .cover h1 { font-family: Georgia, serif; font-size: 28pt; margin-bottom: 10px; }
    .cover .subtitle { font-size: 13pt; color: #555; margin-bottom: 30px; }
    .cover .date { font-size: 10pt; color: #888; }

    /* Section breaks */
    .page-break { page-break-before: always; }

    /* Section headings */
    h2 {
      font-family: Georgia, serif;
      font-size: 14pt;
      color: #1a1a1a;
      margin-bottom: 12px;
      padding-bottom: 6px;
      border-bottom: 2px solid #2c5282;
    }

    h3 {
      font-size: 10pt;
      color: #2c5282;
      margin: 14px 0 6px;
    }

    p { margin: 8px 0; }

    /* Financial tables */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 8.5pt;
      margin: 10px 0;
    }

    th, td {
      padding: 5px 6px;
      border: 1px solid #ddd;
      vertical-align: middle;
    }

    th {
      background: #f0f0f0;
      font-weight: 700;
      text-align: center;
      font-size: 8pt;
    }

    td { text-align: right; }
    td.label { text-align: left; font-weight: 600; }
    td.sublabel { text-align: left; padding-left: 16px; }
    td.pct { color: #666; font-size: 7.5pt; }

    tr.subtotal { background: #f7f7f7; font-weight: 700; }
    tr.total { background: #e8eef6; font-weight: 700; }
    tr.divider td { border-top: 2px solid #333; }

    .neg { color: #c53030; }

    /* Methodology text */
    .methodology {
      columns: 2;
      column-gap: 24px;
      font-size: 9pt;
      line-height: 1.55;
    }

    .methodology p { margin-bottom: 8px; }

    /* Intro funding box */
    .funding-box {
      border: 1px solid #ddd;
      padding: 12px 16px;
      margin: 12px 0;
      display: inline-block;
    }

    .funding-box table { border: none; }
    .funding-box td { border: none; padding: 3px 12px; }
  </style>
</head>
<body>
  <div class="sidebar-brand">{{ concept_name or "" }}</div>

  <!-- Cover -->
  <div class="cover">
    <div class="cover-accent"></div>
    <h1>{{ concept_name or "Restaurant" }}</h1>
    <div class="subtitle">Financial Model</div>
    <div class="date">{{ date or "" }}</div>
  </div>

  <!-- Introduction -->
  <div class="page-break">
    <h2>Introduction</h2>
    {% if fm.funding %}
    <p>The financial model is based on {{ "renovation to an existing restaurant space" if fm.meta.service_model != "qsr" else "a quick-service restaurant setup" }}.
    The Opening Budget for the launch is ${{ "{:,.0f}".format(fm.funding.total) }} which allows for all cosmetic renovations, equipment, inventory and Pre-Opening operational costs.</p>
    <p>For purposes of this plan, it is assumed that the company will be funded by a combination of owner equity and bank financing as per below.</p>
    <div class="funding-box">
      <table>
        <tr><td class="label">Equity</td><td>$ {{ "{:,.0f}".format(fm.funding.equity) }}</td></tr>
        <tr><td class="label">Loan</td><td>$ {{ "{:,.0f}".format(fm.funding.loan) }}</td></tr>
        <tr class="total"><td class="label">Total</td><td>$ {{ "{:,.0f}".format(fm.funding.total) }}</td></tr>
      </table>
    </div>
    {% endif %}
  </div>

  <!-- Opening Budget -->
  {% if fm.opening_budget %}
  <div class="page-break">
    <h2>Use of Funds &mdash; Pre-Opening Budget</h2>
    <table>
      <thead>
        <tr><th style="text-align:left;">Category</th><th>Amount</th></tr>
      </thead>
      <tbody>
        <tr><td class="label">Building (Leasehold Improvements)</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.building) }}</td></tr>
        <tr><td class="label">Equipment &amp; Supplies</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.equipment) }}</td></tr>
        <tr><td class="label">Operating Supplies</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.operating_supplies) }}</td></tr>
        <tr><td class="label">Pre-Opening Expenses</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.preopening) }}</td></tr>
        <tr><td class="label">Marketing</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.marketing) }}</td></tr>
        <tr><td class="label">Working Capital</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.working_capital) }}</td></tr>
        <tr><td class="label">Miscellaneous / Financing</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.misc_financing) }}</td></tr>
        <tr class="total"><td class="label">TOTAL</td><td>$ {{ "{:,.0f}".format(fm.opening_budget.total) }}</td></tr>
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- Year 1 Income Statement -->
  <div class="page-break">
    <h2>Year 1 Income Statement</h2>
    <table>
      <thead>
        <tr>
          <th style="text-align:left;">Category</th>
          {% for p in fm.year1_income.periods %}
            <th>P{{ p }}</th>
          {% endfor %}
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="label">Weekly Sales</td>
          {% for ws in fm.year1_income.weekly_sales %}
            <td>$ {{ "{:,.0f}".format(ws) }}</td>
          {% endfor %}
          <td></td>
        </tr>
        <tr class="subtotal">
          <td class="label">REVENUE</td>
          {% for r in fm.year1_income.revenue %}
            <td>$ {{ "{:,.0f}".format(r) }}</td>
          {% endfor %}
          <td>$ {{ "{:,.0f}".format(fm.year1_income.totals.revenue) }}</td>
        </tr>
        <tr>
          <td class="label">Product Cost</td>
          {% for c in fm.year1_income.cogs %}
            <td>$ {{ "{:,.0f}".format(c) }}</td>
          {% endfor %}
          <td>$ {{ "{:,.0f}".format(fm.year1_income.totals.cogs) }}</td>
        </tr>
        <tr class="subtotal">
          <td class="label">GROSS MARGIN</td>
          {% for gm in fm.year1_income.gross_margin %}
            <td>$ {{ "{:,.0f}".format(gm) }}</td>
          {% endfor %}
          <td>$ {{ "{:,.0f}".format(fm.year1_income.totals.gross_margin) }}</td>
        </tr>
        <tr>
          <td class="label">Wages</td>
          {% for w in fm.year1_income.wages %}
            <td>$ {{ "{:,.0f}".format(w) }}</td>
          {% endfor %}
          <td>$ {{ "{:,.0f}".format(fm.year1_income.totals.wages) }}</td>
        </tr>
        <tr>
          <td class="label">Operating Costs</td>
          {% for o in fm.year1_income.operating %}
            <td>$ {{ "{:,.0f}".format(o) }}</td>
          {% endfor %}
          <td>$ {{ "{:,.0f}".format(fm.year1_income.totals.operating) }}</td>
        </tr>
        <tr>
          <td class="label">Fixed Costs</td>
          {% for f in fm.year1_income.fixed %}
            <td>$ {{ "{:,.0f}".format(f) }}</td>
          {% endfor %}
          <td>$ {{ "{:,.0f}".format(fm.year1_income.totals.fixed) }}</td>
        </tr>
        <tr class="total divider">
          <td class="label">EBITDA</td>
          {% for e in fm.year1_income.ebitda %}
            <td class="{{ 'neg' if e < 0 else '' }}">$ {{ "{:,.0f}".format(e) }}</td>
          {% endfor %}
          <td class="{{ 'neg' if fm.year1_income.totals.ebitda < 0 else '' }}">$ {{ "{:,.0f}".format(fm.year1_income.totals.ebitda) }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- 5-Year Income Statement -->
  <div class="page-break">
    <h2>5-Year Income Statement</h2>
    <table>
      <thead>
        <tr>
          <th style="text-align:left;"></th>
          {% for y in fm.five_year %}
            <th colspan="2">Year {{ y.year }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        <tr class="subtotal">
          <td class="label">REVENUE</td>
          {% for y in fm.five_year %}
            <td>$ {{ "{:,.0f}".format(y.revenue) }}</td><td class="pct">100.0%</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="label">Product Cost</td>
          {% for y in fm.five_year %}
            <td>$ {{ "{:,.0f}".format(y.cogs) }}</td><td class="pct">{{ y.cogs_pct }}%</td>
          {% endfor %}
        </tr>
        <tr class="subtotal">
          <td class="label">GROSS MARGIN</td>
          {% for y in fm.five_year %}
            <td>$ {{ "{:,.0f}".format(y.gross_margin) }}</td><td class="pct">{{ "%.1f"|format(100 - y.cogs_pct) }}%</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="label">Wages</td>
          {% for y in fm.five_year %}
            <td>$ {{ "{:,.0f}".format(y.wages) }}</td><td class="pct">{{ y.wages_pct }}%</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="label">Operating Costs</td>
          {% for y in fm.five_year %}
            <td>$ {{ "{:,.0f}".format(y.operating) }}</td><td class="pct"></td>
          {% endfor %}
        </tr>
        <tr>
          <td class="label">Fixed Costs</td>
          {% for y in fm.five_year %}
            <td>$ {{ "{:,.0f}".format(y.fixed) }}</td><td class="pct"></td>
          {% endfor %}
        </tr>
        <tr class="total divider">
          <td class="label">NET PROFIT</td>
          {% for y in fm.five_year %}
            <td class="{{ 'neg' if y.net_profit < 0 else '' }}">$ {{ "{:,.0f}".format(y.net_profit) }}</td>
            <td class="pct {{ 'neg' if y.net_profit_pct < 0 else '' }}">{{ y.net_profit_pct }}%</td>
          {% endfor %}
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Balance Sheet -->
  <div class="page-break">
    <h2>Balance Sheet</h2>
    <table>
      <thead>
        <tr>
          <th style="text-align:left;"></th>
          {% for bs in fm.balance_sheets %}
            <th>{{ bs.label }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        <tr><td class="label" colspan="{{ fm.balance_sheets|length + 1 }}" style="background:#e8eef6;">ASSETS</td></tr>
        <tr>
          <td class="sublabel">Cash</td>
          {% for bs in fm.balance_sheets %}
            <td>$ {{ "{:,.0f}".format(bs.cash) }}</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="sublabel">Inventory</td>
          {% for bs in fm.balance_sheets %}
            <td>$ {{ "{:,.0f}".format(bs.inventory) }}</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="sublabel">Capital Assets (net)</td>
          {% for bs in fm.balance_sheets %}
            <td>$ {{ "{:,.0f}".format(bs.capital_assets) }}</td>
          {% endfor %}
        </tr>
        <tr class="subtotal">
          <td class="label">TOTAL ASSETS</td>
          {% for bs in fm.balance_sheets %}
            <td>$ {{ "{:,.0f}".format(bs.total_assets) }}</td>
          {% endfor %}
        </tr>
        <tr><td class="label" colspan="{{ fm.balance_sheets|length + 1 }}" style="background:#e8eef6;">LIABILITIES &amp; EQUITY</td></tr>
        <tr>
          <td class="sublabel">Bank Loan</td>
          {% for bs in fm.balance_sheets %}
            <td>$ {{ "{:,.0f}".format(bs.loan) }}</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="sublabel">Shareholder Equity</td>
          {% for bs in fm.balance_sheets %}
            <td>$ {{ "{:,.0f}".format(bs.equity) }}</td>
          {% endfor %}
        </tr>
        <tr>
          <td class="sublabel">Retained Earnings</td>
          {% for bs in fm.balance_sheets %}
            <td class="{{ 'neg' if bs.retained_earnings < 0 else '' }}">$ {{ "{:,.0f}".format(bs.retained_earnings) }}</td>
          {% endfor %}
        </tr>
      </tbody>
    </table>
  </div>

</body>
</html>
```

- [ ] **Step 2: Verify template syntax**

Run: `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); t = env.get_template('financial_pdf.html'); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add templates/financial_pdf.html
git commit -m "feat: add financial model PDF template with income statement, 5-year, and balance sheet"
```

---

## Task 12: Add financial PDF export route to app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add the financial PDF export route**

Add after the existing PDF export route:

```python
@app.route("/plans/<plan_id>/export/financial-pdf")
def plan_export_financial_pdf(plan_id):
    plan_record = _get_plan_or_404(plan_id)
    if not plan_record:
        return "Plan not found", 404

    import json as _json
    plan_json = plan_record.get("plan_json")
    if not plan_json:
        return "Plan data not available", 400

    plan_data = _json.loads(plan_json) if isinstance(plan_json, str) else plan_json

    # Get concept data (normalized intake)
    normalized_json = plan_record.get("normalized_intake_json")
    if not normalized_json:
        return "Normalized intake not available for financial model", 400
    concept = _json.loads(normalized_json) if isinstance(normalized_json, str) else normalized_json

    # Generate financial model
    from orchestration.financial_model_generator import generate_financial_model
    fm = generate_financial_model(concept, plan_data.get("derived_financials"))

    concept_name = plan_data.get("plan_meta", {}).get("concept_name", "Restaurant")
    date_str = (plan_data.get("plan_meta", {}).get("created_at", "") or "")[:10]

    # Wrap dicts for Jinja2 dot-notation access
    fm_wrapped = _wrap_plan(fm)

    html = render_template(
        "financial_pdf.html",
        fm=fm_wrapped,
        concept_name=concept_name,
        date=date_str,
    )

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded", timeout=60_000)

        pdf_bytes = page.pdf(
            format="A4",
            landscape=True,
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template='<div style="width:100%;text-align:center;font-size:9px;color:#999;"><span class="pageNumber"></span></div>',
            margin={"top": "18mm", "bottom": "22mm", "left": "15mm", "right": "15mm"},
        )
        browser.close()

    safe_name = "".join(c for c in (concept_name or "plan") if c.isalnum() or c in " _-").strip() or "plan"
    filename = f"ConceptLB_{safe_name}_FinancialModel.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
```

- [ ] **Step 2: Add Financial Model download button to plan_detail.html**

Find the existing PDF export button in `templates/plan_detail.html` and add a second button next to it:

```html
<a href="/plans/{{ plan.id }}/export/financial-pdf" class="btn">Download Financial Model PDF</a>
```

- [ ] **Step 3: Test manually**

Start Flask, generate a plan with financial anchors filled in (opening_budget_usd, etc.), then visit `/plans/<id>/export/financial-pdf`. Verify:
- Landscape A4 format
- Cover page with concept name and "Financial Model"
- Opening budget table
- Year 1 income statement with 13 periods
- 5-year projections
- Balance sheet

- [ ] **Step 4: Commit**

```bash
git add app.py templates/plan_detail.html
git commit -m "feat: add financial model PDF export route and download button"
```

---

## Task 13: Integration testing — generate a full plan and verify both PDFs

**Files:** None (manual testing)

- [ ] **Step 1: Start the server and generate a test plan**

Run: `python app.py`

Go to `http://localhost:5000/wizard` and fill in a test concept with:
- Concept name: "Olive & Thyme"
- Cuisine: Modern Mediterranean
- Country: Lebanon, City: Beirut
- Alcohol: Yes
- Meal periods: Morning, Lunch, Dinner
- Opening budget: $300,000
- Expected daily orders: 150
- Avg ticket: $20
- Monthly rent: $4,000

Submit and wait for generation to complete.

- [ ] **Step 2: Download the Business Plan PDF**

Visit `/plans/<id>/export/pdf` and verify:
- Professional white-background design
- Cover page, TOC, sidebar branding
- Full menu sections with dish names and ingredients
- Equipment list with 30+ items
- SWOT with 4+ points per quadrant
- Page numbers in footer

- [ ] **Step 3: Download the Financial Model PDF**

Visit `/plans/<id>/export/financial-pdf` and verify:
- Landscape format
- Opening budget breakdown
- Year 1 income statement with 13 periods and ramp-up
- 5-year projections showing growth
- Balance sheet with asset depreciation and loan amortization

- [ ] **Step 4: Commit any fixes**

If any issues found during testing, fix and commit:
```bash
git add -A
git commit -m "fix: address integration test findings"
```

---

## Summary

| Task | What | Priority |
|------|------|----------|
| 1 | MenuItemsBlock Pydantic schema | P1 |
| 2 | menu_items web template block | P1 |
| 3 | Print-optimized block macros | P0 |
| 4 | Professional PDF template | P0 |
| 5 | Update PDF export route | P0 |
| 6 | Section specs: word budgets + prompt hints | P1 + P3 |
| 7 | Prompt overhaul + token limits | P1 + P3 |
| 8 | Financial fields in schema + wizard | P2 |
| 9 | Market data module | P3 |
| 10 | Financial model generator | P2 |
| 11 | Financial model PDF template | P2 |
| 12 | Financial PDF export route | P2 |
| 13 | Integration testing | All |
