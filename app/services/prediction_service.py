"""
Smart Prediction Engine — Phase 8
Implements SMA, WMA, festival calendar, 30-day learning gate,
confidence range, risk classification, and plain-language reasons.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
import math

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from app.models.product import Product, Inventory
from app.models.sale import Sale, SaleItem
from app.models.system import PredictionHistory
from app.schemas.predictions import PredictionOut, PredictionOverride, PredictionsListOut
import os
LEARNING_PHASE_DAYS = int(os.getenv("LEARNING_PHASE_DAYS", "30"))


# ─────────────────────────────────────────────
# FESTIVAL CALENDAR  (Indian festivals, 2025-2027)
# Category multipliers: high-demand categories during each festival
# ─────────────────────────────────────────────

FESTIVAL_CALENDAR = [
    {"name": "Diwali",     "date": date(2025, 10, 20), "window": 14, "multipliers": {"grocery": 1.5, "dairy": 1.4, "snacks": 1.8, "personal": 1.3}},
    {"name": "Diwali",     "date": date(2026, 11,  8), "window": 14, "multipliers": {"grocery": 1.5, "dairy": 1.4, "snacks": 1.8, "personal": 1.3}},
    {"name": "Diwali",     "date": date(2027, 10, 29), "window": 14, "multipliers": {"grocery": 1.5, "dairy": 1.4, "snacks": 1.8, "personal": 1.3}},
    {"name": "Navratri",   "date": date(2025, 10,  2), "window": 9,  "multipliers": {"grocery": 1.4, "dairy": 1.3, "snacks": 1.5}},
    {"name": "Navratri",   "date": date(2026,  9, 21), "window": 9,  "multipliers": {"grocery": 1.4, "dairy": 1.3, "snacks": 1.5}},
    {"name": "Holi",       "date": date(2026,  3, 13), "window": 7,  "multipliers": {"snacks": 1.6, "beverages": 1.5, "personal": 1.2}},
    {"name": "Holi",       "date": date(2027,  3,  2), "window": 7,  "multipliers": {"snacks": 1.6, "beverages": 1.5, "personal": 1.2}},
    {"name": "Eid",        "date": date(2026,  3, 31), "window": 7,  "multipliers": {"grocery": 1.5, "dairy": 1.3, "snacks": 1.6}},
    {"name": "Christmas",  "date": date(2025, 12, 25), "window": 7,  "multipliers": {"snacks": 1.4, "beverages": 1.3}},
    {"name": "Christmas",  "date": date(2026, 12, 25), "window": 7,  "multipliers": {"snacks": 1.4, "beverages": 1.3}},
    {"name": "Makar Sankranti", "date": date(2026, 1, 14), "window": 5, "multipliers": {"grocery": 1.3, "snacks": 1.4}},
]


def _get_festival_boost(category: str) -> Tuple[bool, Optional[str], float]:
    """Check if today is within the window of any upcoming festival."""
    today = date.today()
    for festival in FESTIVAL_CALENDAR:
        fest_date = festival["date"]
        window = festival["window"]
        days_away = (fest_date - today).days
        if 0 <= days_away <= window:
            multiplier = festival["multipliers"].get(category, 1.0)
            if multiplier > 1.0:
                return True, festival["name"], multiplier
    return False, None, 1.0


# ─────────────────────────────────────────────
# SALES HISTORY  (weekly buckets)
# ─────────────────────────────────────────────

def _get_weekly_sales(db: Session, product_id: int, weeks: int = 8) -> List[float]:
    """
    Returns a list of weekly unit sales, oldest first.
    Each element = total units sold in that 7-day period.
    """
    today = date.today()
    weekly = []
    for i in range(weeks - 1, -1, -1):
        week_end = today - timedelta(days=i * 7)
        week_start = week_end - timedelta(days=7)
        qty = db.query(func.coalesce(func.sum(SaleItem.quantity), 0))\
            .join(Sale)\
            .filter(
                SaleItem.product_id == product_id,
                func.date(Sale.sale_date) >= week_start,
                func.date(Sale.sale_date) < week_end,
            ).scalar()
        weekly.append(float(qty or 0))
    return weekly


# ─────────────────────────────────────────────
# ALGORITHMS
# ─────────────────────────────────────────────

def _sma(data: List[float], n: int = 4) -> float:
    """Simple Moving Average of last n periods."""
    recent = data[-n:] if len(data) >= n else data
    return sum(recent) / len(recent) if recent else 0.0


def _wma(data: List[float], n: int = 4) -> float:
    """Weighted Moving Average — more weight on recent weeks."""
    recent = data[-n:] if len(data) >= n else data
    if not recent:
        return 0.0
    weights = list(range(1, len(recent) + 1))
    return sum(v * w for v, w in zip(recent, weights)) / sum(weights)


def _confidence_band(forecast: float, data: List[float]) -> Tuple[int, int]:
    """±15% of forecast, widened by variance in data."""
    if len(data) >= 2:
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std = math.sqrt(variance)
        band = max(forecast * 0.15, std)
    else:
        band = forecast * 0.2
    low = max(0, int(forecast - band))
    high = int(forecast + band)
    return low, high


def _risk_level(current_stock: int, reorder_level: int, forecast: float) -> str:
    if current_stock <= 0:
        return "high"
    if current_stock <= reorder_level or current_stock < forecast * 0.5:
        return "medium"
    return "low"


def _plain_reason(
    product_name: str,
    method: str,
    forecast: float,
    weekly_data: List[float],
    festival_name: Optional[str],
) -> str:
    non_zero = [w for w in weekly_data if w > 0]
    avg = sum(non_zero) / len(non_zero) if non_zero else 0

    if festival_name:
        return (
            f"{festival_name} is coming up. Based on past sales, "
            f"expect demand for {product_name} to rise — we suggest stocking {int(forecast)} units this week."
        )
    if avg == 0:
        return f"No sales recorded for {product_name} yet. Add some sales first for predictions to improve."
    trend = ""
    if len(weekly_data) >= 2 and weekly_data[-1] > weekly_data[-2] * 1.1:
        trend = " Sales are trending upward recently."
    elif len(weekly_data) >= 2 and weekly_data[-1] < weekly_data[-2] * 0.9:
        trend = " Sales have slowed recently."
    return (
        f"Based on the last {len(weekly_data)} weeks of sales history, "
        f"{product_name} averages {int(avg)} units per week.{trend} "
        f"We recommend stocking {int(forecast)} units for next week."
    )


# ─────────────────────────────────────────────
# CORE: GENERATE PREDICTION FOR ONE PRODUCT
# ─────────────────────────────────────────────

def _predict_product(db: Session, product: Product) -> PredictionOut:
    today = date.today()
    created = product.created_at.date() if product.created_at else today
    age_days = (today - created).days
    learning_total = LEARNING_PHASE_DAYS
    inv = product.inventory
    current_stock = inv.current_stock if inv else 0
    category = product.category.category_name if product.category else "grocery"

    # Learning phase check
    if age_days < learning_total:
        return PredictionOut(
            product_id=product.product_id,
            product_name=product.name,
            category=category,
            status="learning",
            learning_days_complete=age_days,
            learning_days_total=learning_total,
            reason=f"StorePilot is learning your sales patterns for {product.name}. "
                   f"{age_days} of {learning_total} days complete — predictions unlock soon.",
            current_stock=current_stock,
            risk_level=_risk_level(current_stock, product.reorder_level, 0),
        )

    # Get sales history
    weekly_data = _get_weekly_sales(db, product.product_id, weeks=8)
    total_sold = sum(weekly_data)

    # If no sales at all, show a gentle nudge
    if total_sold == 0:
        return PredictionOut(
            product_id=product.product_id,
            product_name=product.name,
            category=category,
            status="learning",
            learning_days_complete=age_days,
            learning_days_total=learning_total,
            reason=f"No sales recorded for {product.name} yet. Start billing to unlock predictions.",
            current_stock=current_stock,
            risk_level=_risk_level(current_stock, product.reorder_level, 0),
        )

    # Pick algorithm: WMA if recent trend changed, else SMA
    recent_avg = _sma(weekly_data[-2:], n=2)
    older_avg  = _sma(weekly_data[:4], n=4)
    use_wma = abs(recent_avg - older_avg) > older_avg * 0.2 if older_avg > 0 else False
    method = "WMA" if use_wma else "SMA"
    base_forecast = _wma(weekly_data) if use_wma else _sma(weekly_data)

    # Festival multiplier
    has_festival, festival_name, multiplier = _get_festival_boost(category)
    forecast = base_forecast * multiplier

    # Confidence band
    conf_low, conf_high = _confidence_band(forecast, weekly_data)

    # Reorder quantity: avg daily * 7 day lead time + safety stock
    avg_daily = sum(weekly_data) / (len(weekly_data) * 7)
    lead_time = 7
    safety_stock = int(avg_daily * 3)
    reorder_qty = int(avg_daily * lead_time) + safety_stock

    reason = _plain_reason(product.name, method, forecast, weekly_data, festival_name)

    return PredictionOut(
        product_id=product.product_id,
        product_name=product.name,
        category=category,
        status="ready",
        learning_days_complete=age_days,
        learning_days_total=learning_total,
        forecast_qty=max(1, int(forecast)),
        confidence_low=conf_low,
        confidence_high=conf_high,
        method_used=method,
        reason=reason,
        reorder_qty=reorder_qty,
        current_stock=current_stock,
        risk_level=_risk_level(current_stock, product.reorder_level, forecast),
        festival_boost=has_festival,
        festival_name=festival_name,
        festival_multiplier=round(multiplier, 2) if has_festival else None,
    )


# ─────────────────────────────────────────────
# PUBLIC: GET ALL PREDICTIONS
# ─────────────────────────────────────────────

def get_all_predictions(db: Session, store_id: int) -> PredictionsListOut:
    products = db.query(Product).filter(
        Product.store_id == store_id,
        Product.is_active == True,
    ).all()

    today = date.today()
    store_age = 0
    if products:
        oldest = min(p.created_at.date() for p in products if p.created_at)
        store_age = (today - oldest).days

    learning = []
    ready = []
    for p in products:
        pred = _predict_product(db, p)
        if pred.status == "learning":
            learning.append(pred)
        else:
            ready.append(pred)

    # Sort ready by risk level: high → medium → low
    risk_order = {"high": 0, "medium": 1, "low": 2}
    ready.sort(key=lambda x: risk_order.get(x.risk_level, 3))

    return PredictionsListOut(
        learning=learning,
        ready=ready,
        total_products=len(products),
        store_age_days=store_age,
    )


# ─────────────────────────────────────────────
# PUBLIC: GET SINGLE PREDICTION
# ─────────────────────────────────────────────

def get_prediction(db: Session, store_id: int, product_id: int) -> PredictionOut:
    product = db.query(Product).filter(
        Product.product_id == product_id,
        Product.store_id == store_id,
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _predict_product(db, product)


# ─────────────────────────────────────────────
# PUBLIC: OVERRIDE / CONFIRM
# ─────────────────────────────────────────────

def override_prediction(
    db: Session,
    store_id: int,
    product_id: int,
    data: PredictionOverride,
) -> dict:
    product = db.query(Product).filter(
        Product.product_id == product_id,
        Product.store_id == store_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Log to prediction_history for the self-correction loop
    entry = PredictionHistory(
        product_id=product_id,
        prediction_date=date.today(),
        method_used="OVERRIDE",
        forecast_qty=data.adjusted_qty,
        confidence_low=data.adjusted_qty,
        confidence_high=data.adjusted_qty,
    )
    db.add(entry)
    db.commit()

    return {
        "product_id": product_id,
        "product_name": product.name,
        "adjusted_qty": data.adjusted_qty,
        "reason": data.reason,
        "message": f"Prediction for {product.name} confirmed as {data.adjusted_qty} units.",
    }


# ─────────────────────────────────────────────
# SCHEDULER JOB (called daily by APScheduler)
# ─────────────────────────────────────────────

def run_daily_predictions(db: Session, store_id: int):
    """Run and save predictions for all products in a store."""
    products = db.query(Product).filter(
        Product.store_id == store_id,
        Product.is_active == True,
    ).all()

    for product in products:
        pred = _predict_product(db, product)
        if pred.status == "ready" and pred.forecast_qty:
            entry = PredictionHistory(
                product_id=product.product_id,
                prediction_date=date.today(),
                method_used=pred.method_used or "SMA",
                forecast_qty=pred.forecast_qty,
                confidence_low=pred.confidence_low,
                confidence_high=pred.confidence_high,
            )
            db.add(entry)
    db.commit()