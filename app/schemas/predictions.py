from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class PredictionOut(BaseModel):
    product_id: int
    product_name: str
    category: str

    # Status
    status: str               # "learning" | "ready"
    learning_days_complete: int
    learning_days_total: int

    # Forecast (only when status = ready)
    forecast_qty: Optional[int] = None
    confidence_low: Optional[int] = None
    confidence_high: Optional[int] = None
    method_used: Optional[str] = None   # SMA / WMA
    reason: str                          # always present, plain language

    # Restock guidance
    reorder_qty: Optional[int] = None
    current_stock: int
    risk_level: str           # "low" | "medium" | "high"

    # Festival info
    festival_boost: bool = False
    festival_name: Optional[str] = None
    festival_multiplier: Optional[float] = None

    class Config:
        from_attributes = True


class PredictionOverride(BaseModel):
    """POST /predictions/{product_id}/override"""
    adjusted_qty: int
    reason: str


class PredictionsListOut(BaseModel):
    learning: List[PredictionOut]
    ready: List[PredictionOut]
    total_products: int
    store_age_days: int