from __future__ import annotations
from typing import Any, Dict, Optional

WEEKS_PER_MONTH = 4.345  # average


def compute_derived_financials(concept: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic calculations based only on anchors.
    If an input is missing, output stays None (no guessing).
    """
    orders = _to_float(concept.get("expected_daily_orders"))
    ticket = _to_float(concept.get("avg_ticket_usd"))
    days_per_week = _to_float(concept.get("operating_days_per_week"))
    rent = _to_float(concept.get("monthly_rent_usd"))
    cogs_pct = _to_float(concept.get("target_cogs_pct"))
    staff_model = concept.get("staff_model")

    # we will NOT guess days/week if missing — keep None (honest)
    days_per_month = None
    if days_per_week is not None:
        days_per_month = days_per_week * WEEKS_PER_MONTH

    monthly_revenue = None
    if orders is not None and ticket is not None and days_per_month is not None:
        monthly_revenue = orders * ticket * days_per_month

    cogs_amount = None
    gross_margin = None
    if monthly_revenue is not None and cogs_pct is not None:
        cogs_amount = monthly_revenue * (cogs_pct / 100.0)
        gross_margin = monthly_revenue - cogs_amount

    contribution_per_order = None
    if ticket is not None and cogs_pct is not None:
        contribution_per_order = ticket * (1.0 - cogs_pct / 100.0)

    payroll_estimate = _payroll_estimate_usd(staff_model)

    fixed_costs_known = _sum_known([rent, payroll_estimate])

    breakeven_orders_per_day = None
    if fixed_costs_known is not None and contribution_per_order and days_per_month:
        daily_fixed = fixed_costs_known / days_per_month
        if contribution_per_order > 0:
            breakeven_orders_per_day = daily_fixed / contribution_per_order

    return {
        "inputs_used": {
            "expected_daily_orders": orders,
            "avg_ticket_usd": ticket,
            "operating_days_per_week": days_per_week,
            "monthly_rent_usd": rent,
            "target_cogs_pct": cogs_pct,
            "staff_model": staff_model,
        },
        "outputs": {
            "days_per_month": _round(days_per_month),
            "monthly_revenue_usd": _round(monthly_revenue),
            "cogs_amount_usd": _round(cogs_amount),
            "gross_margin_usd": _round(gross_margin),
            "fixed_costs_usd_known_only": _round(fixed_costs_known),
            "breakeven_orders_per_day": _round(breakeven_orders_per_day, 2),
        },
    }


def _payroll_estimate_usd(staff_model: Any) -> Optional[float]:
    # Simple baseline lookup. Can be moved to settings later.
    mapping = {
        "lean": 2500.0,
        "standard": 4500.0,
        "full": 7000.0,
        "custom": None,
        None: None,
    }
    return mapping.get(staff_model, None)


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _sum_known(values: list[Optional[float]]) -> Optional[float]:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def _round(x: Optional[float], nd: int = 0) -> Optional[float]:
    if x is None:
        return None
    return round(float(x), nd)