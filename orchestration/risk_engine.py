from schemas.risk_schema import RiskReport, RiskFlag


def _first_number(*values, default=0):
    """
    Return the first non-null value.
    Treats 0 as a valid value.
    """
    for value in values:
        if value is None:
            continue
        return value
    return default


def evaluate_risk(concept, financials) -> RiskReport:
    flags = []
    score = 0

    # ------------------------------------------------
    # FINANCIAL OUTPUTS MAPPING
    # Your financial engine returns:
    # {
    #   "inputs_used": {...},
    #   "outputs": {
    #       "monthly_revenue_usd": ...,
    #       "breakeven_orders_per_day": ...,
    #       "fixed_costs_usd_known_only": ...,
    #       ...
    #   }
    # }
    # ------------------------------------------------

    outputs = financials.get("outputs", {}) if isinstance(financials, dict) else {}

    monthly_revenue = _first_number(
        outputs.get("monthly_revenue_usd"),
        financials.get("monthly_revenue"),
        financials.get("revenue_monthly"),
        default=0,
    )

    break_even_orders_per_day = _first_number(
        outputs.get("breakeven_orders_per_day"),
        financials.get("break_even_orders_per_day"),
        default=0,
    )

    fixed_costs_known = _first_number(
        outputs.get("fixed_costs_usd_known_only"),
        financials.get("fixed_costs_usd_known_only"),
        default=0,
    )

    # ------------------------------------------------
    # CONCEPT INPUT MAPPING
    # ------------------------------------------------

    monthly_rent = _first_number(
        concept.get("monthly_rent_usd"),
        concept.get("monthly_rent"),
        concept.get("rent_usd"),
        concept.get("rent"),
        default=0,
    )

    seats = _first_number(
        concept.get("seating_capacity"),
        concept.get("seats"),
        concept.get("seat_count"),
        default=0,
    )

    capex = _first_number(
        concept.get("capex_budget_usd"),
        concept.get("capex_budget"),
        concept.get("capex"),
        default=0,
    )

    avg_ticket = _first_number(
        concept.get("avg_ticket_usd"),
        concept.get("avg_ticket"),
        default=0,
    )

    expected_daily_orders = _first_number(
        concept.get("expected_daily_orders"),
        concept.get("orders_per_day"),
        default=0,
    )

    size_sqm = _first_number(
        concept.get("size_sqm"),
        concept.get("area_sqm"),
        default=0,
    )

    service_model = (concept.get("service_model") or "").strip().lower()
    kitchen_type = (concept.get("kitchen_type") or "").strip().lower()

    # ------------------------------------------------
    # DERIVED RATIOS
    # ------------------------------------------------

    rent_ratio = 0
    if monthly_revenue > 0:
        rent_ratio = monthly_rent / monthly_revenue

    capex_per_seat = 0
    if seats > 0:
        capex_per_seat = capex / seats

    capex_per_sqm = 0
    if size_sqm > 0:
        capex_per_sqm = capex / size_sqm

    revenue_per_sqm = 0
    if size_sqm > 0:
        revenue_per_sqm = monthly_revenue / size_sqm

    orders_per_seat = 0
    if seats > 0:
        orders_per_seat = expected_daily_orders / seats

    sqm_per_seat = 0
    if size_sqm > 0 and seats > 0:
        sqm_per_seat = size_sqm / seats

    # ------------------------------------------------
    # RENT BURDEN CHECK
    # ------------------------------------------------

    if rent_ratio > 0.18:
        flags.append(
            RiskFlag(
                code="rent_extreme",
                severity="critical",
                title="Rent is extremely high",
                message="Rent exceeds 18% of projected revenue. The concept is likely unsustainable at this revenue level.",
            )
        )
        score += 40

    elif rent_ratio > 0.12:
        flags.append(
            RiskFlag(
                code="rent_high",
                severity="danger",
                title="High rent burden",
                message="Rent exceeds a healthy restaurant threshold of 12% of projected revenue.",
            )
        )
        score += 20

    # ------------------------------------------------
    # CAPEX PER SEAT CHECK
    # ------------------------------------------------

    if seats > 0:
        if capex_per_seat < 2000:
            flags.append(
                RiskFlag(
                    code="capex_unrealistic_per_seat",
                    severity="critical",
                    title="Capex too low for seat count",
                    message="Capex per seat is extremely low and unlikely to support fit-out, equipment, and launch requirements.",
                )
            )
            score += 35

        elif capex_per_seat < 4000:
            flags.append(
                RiskFlag(
                    code="capex_low_per_seat",
                    severity="warning",
                    title="Capex per seat is low",
                    message="Budget may be insufficient for a typical restaurant build-out at the proposed scale.",
                )
            )
            score += 10

    # ------------------------------------------------
    # CAPEX PER SQM CHECK
    # ------------------------------------------------

    if size_sqm > 0:
        if capex_per_sqm < 200:
            flags.append(
                RiskFlag(
                    code="capex_unrealistic_per_sqm",
                    severity="critical",
                    title="Capex too low for restaurant size",
                    message="Capex per sqm is extremely low for a realistic restaurant fit-out.",
                )
            )
            score += 35

        elif capex_per_sqm < 500:
            flags.append(
                RiskFlag(
                    code="capex_low_per_sqm",
                    severity="warning",
                    title="Capex per sqm is low",
                    message="Capex per sqm looks weak relative to the proposed restaurant footprint.",
                )
            )
            score += 10

    # ------------------------------------------------
    # BREAK-EVEN CHECK
    # ------------------------------------------------

    if break_even_orders_per_day > 0 and expected_daily_orders > 0:
        if break_even_orders_per_day > expected_daily_orders:
            flags.append(
                RiskFlag(
                    code="breakeven_unreachable",
                    severity="critical",
                    title="Break-even volume exceeds projected demand",
                    message="Projected daily orders are below the estimated break-even orders per day.",
                )
            )
            score += 50

    # ------------------------------------------------
    # SPACE EFFICIENCY CHECK
    # ------------------------------------------------

    if sqm_per_seat > 8:
        flags.append(
            RiskFlag(
                code="space_efficiency_low",
                severity="warning",
                title="Space efficiency is low",
                message="The venue size is large relative to the seat count, which may weaken revenue productivity unless this is intentionally delivery-led or production-heavy.",
            )
        )
        score += 10

    # ------------------------------------------------
    # REVENUE DENSITY CHECK
    # ------------------------------------------------

    if size_sqm > 0 and revenue_per_sqm < 120:
        flags.append(
            RiskFlag(
                code="revenue_density_low",
                severity="danger",
                title="Revenue density is low",
                message="Projected monthly revenue appears weak relative to the size of the location.",
            )
        )
        score += 20

    # ------------------------------------------------
    # THROUGHPUT / UTILIZATION SANITY CHECK
    # ------------------------------------------------

    if seats > 0 and expected_daily_orders > 0:
        if service_model == "qsr":
            if orders_per_seat < 2:
                flags.append(
                    RiskFlag(
                        code="throughput_low_for_qsr",
                        severity="warning",
                        title="Throughput looks low for a QSR format",
                        message="Projected daily orders appear low relative to seat count for a quick-service model.",
                    )
                )
                score += 10

        elif service_model == "hybrid":
            if orders_per_seat < 1.5:
                flags.append(
                    RiskFlag(
                        code="throughput_low_for_hybrid",
                        severity="warning",
                        title="Throughput looks low for the proposed format",
                        message="Projected daily orders appear low relative to the proposed footprint and seat count.",
                    )
                )
                score += 10

        elif service_model == "dine_in":
            if orders_per_seat < 1:
                flags.append(
                    RiskFlag(
                        code="throughput_low_for_dine_in",
                        severity="warning",
                        title="Throughput looks low for dine-in",
                        message="Projected daily covers appear low for the seat count and operating model.",
                    )
                )
                score += 10

    # ------------------------------------------------
    # FULL-LINE KITCHEN VS CAPEX CHECK
    # ------------------------------------------------

    if kitchen_type == "full_line" and capex < 50000:
        flags.append(
            RiskFlag(
                code="full_line_kitchen_underbudgeted",
                severity="danger",
                title="Full-line kitchen may be under-budgeted",
                message="A full-line kitchen usually requires a stronger capital budget than the one provided.",
            )
        )
        score += 20

    # ------------------------------------------------
    # LOW ABSOLUTE REVENUE VS KNOWN FIXED COSTS
    # ------------------------------------------------

    if monthly_revenue > 0 and fixed_costs_known > 0:
        if monthly_revenue < fixed_costs_known:
            flags.append(
                RiskFlag(
                    code="revenue_below_known_fixed_costs",
                    severity="critical",
                    title="Revenue is below known fixed costs",
                    message="Projected monthly revenue is below the known monthly fixed costs before considering additional overheads.",
                )
            )
            score += 35

    # ------------------------------------------------
    # FINAL RISK LEVEL
    # ------------------------------------------------
    score = min(score, 100)
    if score >= 80:
        level = "black"
    elif score >= 50:
        level = "red"
    elif score >= 25:
        level = "yellow"
    else:
        level = "green"

    dimension_scores = {
        "capital": round(capex_per_seat, 2) if capex_per_seat else 0,
        "rent_ratio": round(rent_ratio, 3),
        "capex_per_sqm": round(capex_per_sqm, 2) if capex_per_sqm else 0,
        "revenue_per_sqm": round(revenue_per_sqm, 2) if revenue_per_sqm else 0,
        "orders_per_seat": round(orders_per_seat, 2) if orders_per_seat else 0,
        "break_even_orders_per_day": round(break_even_orders_per_day, 2) if break_even_orders_per_day else 0,
        "fixed_costs_known": round(fixed_costs_known, 2) if fixed_costs_known else 0,
    }

    return RiskReport(
        risk_level=level,
        risk_score=score,
        dimension_scores=dimension_scores,
        flags=flags,
    )