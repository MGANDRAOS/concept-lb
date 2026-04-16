"""
orchestration/financial_model_generator.py
Generates a complete financial model from concept data.
All numbers are deterministic. AI is only used for narrative methodology text.
"""

import math
from typing import Dict, List, Optional, Any

try:
    from orchestration.openai_client import call_model_json
except ImportError:
    call_model_json = None  # Optional — only needed for AI narrative generation


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

    # ── 15. Detailed budget sub-items (for methodology pages) ──
    size_sqm = concept.get("size_sqm", 100)
    budget_detail = None
    if budget_breakdown:
        bld = budget_breakdown.get("building", 0)
        eqp = budget_breakdown.get("equipment", 0)
        ops = budget_breakdown.get("operating_supplies", 0)
        pre = budget_breakdown.get("preopening", 0)
        mkt = budget_breakdown.get("marketing", 0)
        wc = budget_breakdown.get("working_capital", 0)
        misc = budget_breakdown.get("misc_financing", 0)

        budget_detail = {
            "building": [
                {"item": "Interior Build Out", "amount": round(bld * 0.85), "note": f"Budgeted at ~${round(bld * 0.85 / max(size_sqm, 1))}/sqm for the space"},
                {"item": "Hood / Venting", "amount": round(bld * 0.05), "note": "Allowance for ventilation system"},
                {"item": "Design & Engineering Fees", "amount": round(bld * 0.10), "note": "Professional design and engineering"},
            ],
            "equipment": [
                {"item": "Kitchen Equipment", "amount": round(eqp * 0.55), "note": "All required kitchen equipment as per listing"},
                {"item": "Bar Equipment", "amount": round(eqp * 0.12) if has_alcohol else 0, "note": "Bar equipment and tools"},
                {"item": "Chairs / Tables", "amount": round(eqp * 0.10), "note": "Dining furniture"},
                {"item": "Detail Furnishings", "amount": round(eqp * 0.04), "note": "Miscellaneous wall finishes and accents"},
                {"item": "Audio-Visual", "amount": round(eqp * 0.03), "note": "Sound system within the space"},
                {"item": "Point-of-Sale System", "amount": round(eqp * 0.05), "note": "POS hardware and initial setup"},
                {"item": "Signage", "amount": round(eqp * 0.05), "note": "Exterior and interior signage"},
                {"item": "Office Equipment", "amount": round(eqp * 0.03), "note": "Office furniture, computer, printer"},
                {"item": "Security System", "amount": round(eqp * 0.015), "note": "Security cameras and alarm"},
                {"item": "Telephone System", "amount": round(eqp * 0.015), "note": "Phone and internet setup"},
            ],
            "operating_supplies": [
                {"item": "Smallwares / Glasswares / Kitchen Supplies", "amount": round(ops * 0.65), "note": "Initial kitchen supplies"},
                {"item": "Paper Products", "amount": round(ops * 0.15), "note": "Initial takeout packaging and paper supplies"},
                {"item": "Linen / Kitchen Uniform", "amount": round(ops * 0.05), "note": "Kitchen rags and uniforms"},
                {"item": "Menus / Menu Boards", "amount": round(ops * 0.08), "note": "Menu printing and signage"},
                {"item": "Office Supplies", "amount": round(ops * 0.04), "note": "General office supplies"},
                {"item": "Misc FOH / BOH", "amount": round(ops * 0.03), "note": "Miscellaneous front and back of house"},
            ],
            "preopening": [
                {"item": "Management Pre-Opening Labour", "amount": round(pre * 0.55), "note": "Management training period (4-8 weeks)"},
                {"item": "FOH Training Labour", "amount": round(pre * 0.18), "note": "Front of house staff training"},
                {"item": "BOH Training Labour", "amount": round(pre * 0.14), "note": "Back of house staff training"},
                {"item": "Training Food & Materials", "amount": round(pre * 0.06), "note": "Menu development and training supplies"},
                {"item": "Renovation Operational Costs", "amount": round(pre * 0.04), "note": "Costs during renovation period"},
                {"item": "Recruitment Advertising", "amount": round(pre * 0.03), "note": "Job postings and hiring costs"},
            ],
            "marketing": [
                {"item": "Media / PR Advertising", "amount": round(mkt * 0.45), "note": "Pre-opening marketing and social media"},
                {"item": "Website", "amount": round(mkt * 0.40), "note": "Website design and development"},
                {"item": "Brand Development", "amount": round(mkt * 0.15), "note": "Logo, brand standards, visual identity"},
            ],
            "working_capital": [
                {"item": "Inventory - Food", "amount": round(wc * 0.40), "note": "Initial food product inventory"},
                {"item": "Inventory - Beverage", "amount": round(wc * 0.30) if has_alcohol else round(wc * 0.15), "note": "Initial beverage inventory"},
                {"item": "Cash on Hand / Floats", "amount": round(wc * 0.30) if has_alcohol else round(wc * 0.55), "note": "Operating cash and register floats"},
            ],
            "misc_financing": [
                {"item": "Licensing Fees", "amount": round(misc * 0.20), "note": "Business and food service licenses"},
                {"item": "Legal Costs", "amount": round(misc * 0.35), "note": "Incorporation, lease review, trademarks"},
                {"item": "Rent Deposit", "amount": round(misc * 0.35), "note": "Security deposit on lease"},
                {"item": "Utilities / Phone Deposit", "amount": round(misc * 0.10), "note": "Utility account setup deposits"},
            ],
        }

    # ── 16. Operating cost detail breakdown ──────────────────
    operating_cost_detail = [
        {"item": "Smallwares / Glasswares", "pct": 0.5, "note": "Normal replacement amounts"},
        {"item": "Paper Products", "pct": 0.3, "note": "Normal replacement amounts"},
        {"item": "Credit Card Commissions", "pct": 1.8, "note": "Based on 60% credit card payment split"},
        {"item": "Linen / Kitchen Uniform", "pct": 0.2, "note": "Ongoing replacement"},
        {"item": "Cleaning / Dishwasher", "pct": 0.4, "note": "Chemical and cleaning supplies"},
        {"item": "Marketing", "pct": 1.5, "note": "Ongoing marketing initiatives"},
        {"item": "Telephone", "pct": None, "fixed": 200, "note": "2 lines and cellphone"},
        {"item": "Repairs & Maintenance", "pct": 0.5, "note": "Year 1 (increases to 1.0% in Year 2+ as warranties expire)"},
        {"item": "Office / POS Supplies", "pct": 0.2, "note": "Normal operating amounts"},
        {"item": "Waste Removal", "pct": None, "fixed": 300, "note": "3rd party waste removal services"},
        {"item": "QSAs (Quality/Service giveaways)", "pct": 0.4, "note": "Budgeted at 0.4% of sales"},
        {"item": "Equipment Rental", "pct": None, "fixed": 500, "note": "Dishwasher rental, POS subscriptions"},
    ]

    # ── 17. Wages detail ─────────────────────────────────────
    wages_detail = {
        "mgmt_salary": mgmt_salary,
        "mgmt_positions": [],
        "foh_labor_pct": foh_labor_pct * 100,
        "boh_labor_pct": boh_labor_pct * 100,
        "benefits_pct": benefits_pct * 100,
    }
    if staff_model == "lean":
        wages_detail["mgmt_positions"] = [{"title": "General Manager", "salary": mgmt_salary}]
    elif staff_model == "standard":
        wages_detail["mgmt_positions"] = [
            {"title": "General Manager", "salary": round(mgmt_salary * 0.5)},
            {"title": "Kitchen Manager", "salary": round(mgmt_salary * 0.5)},
        ]
    elif staff_model == "full":
        wages_detail["mgmt_positions"] = [
            {"title": "General Manager", "salary": round(mgmt_salary * 0.33)},
            {"title": "Kitchen Manager", "salary": round(mgmt_salary * 0.33)},
            {"title": "Bar Manager / Supervisor", "salary": round(mgmt_salary * 0.34)},
        ]

    # ── 18. Weekly sales table (covers × check by day and period) ──
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekly_sales_table = {
        "day_names": day_names,
        "covers_by_period": {},
        "sales_by_period": {},
        "total_covers_by_day": weekly_covers_by_day,
        "total_sales_by_day": [],
    }
    total_sales_by_day = [0] * 7
    for period in active_periods:
        covers = covers_by_period.get(period, [0]*7)
        sales = sales_by_period.get(period, [0]*7)
        weekly_sales_table["covers_by_period"][period] = covers
        weekly_sales_table["sales_by_period"][period] = sales
        for d in range(7):
            total_sales_by_day[d] += sales[d] if d < len(sales) else 0
    weekly_sales_table["total_sales_by_day"] = total_sales_by_day
    weekly_sales_table["total_weekly_sales"] = sum(total_sales_by_day)

    return {
        "opening_budget": budget_breakdown,
        "budget_detail": budget_detail,
        "funding": funding,
        "avg_check": avg_check,
        "weekly_covers_by_day": weekly_covers_by_day,
        "covers_by_period": covers_by_period,
        "sales_by_period": sales_by_period,
        "weekly_sales_total": weekly_sales_total,
        "weekly_sales_table": weekly_sales_table,
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
        "operating_cost_detail": operating_cost_detail,
        "wages_detail": wages_detail,
        "meta": {
            "service_model": service_model,
            "has_alcohol": has_alcohol,
            "country": country,
            "currency": concept.get("currency", "USD"),
            "staff_model": staff_model,
            "meal_periods": meal_periods,
            "revenue_growth_pct": growth_pct * 100,
            "ramp_months": ramp_months,
            "ramp_start_pct": ramp_start * 100,
            "size_sqm": size_sqm,
            "monthly_rent": monthly_rent,
            "seating_capacity": concept.get("seating_capacity", 0),
        }
    }
