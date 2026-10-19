from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal


class TopProduct(BaseModel):
    product_id: int
    name: str
    qty_sold: int
    pct: int


class UdharCustomer(BaseModel):
    name: str
    initials: str
    credit_balance: Decimal


class DashboardSummary(BaseModel):
    today_revenue: Decimal
    yesterday_revenue: Decimal
    revenue_change_pct: float
    bills_today: int
    avg_bill_value: Decimal
    items_sold_today: int
    weekly_revenue: List[float]
    estimated_profit: Decimal
    low_stock_count: int
    low_stock_items: List[str]
    expiring_count: int
    expiring_items: List[str]
    pending_udhar: Decimal
    udhar_customer_count: int
    open_pos: int
    top_products: List[TopProduct]
    udhar_total: Decimal
    udhar_oldest_days: int
    udhar_customers: List[UdharCustomer]
    top_prediction_name: Optional[str] = None
    top_prediction_range: Optional[str] = None
    top_prediction_reason: Optional[str] = None
    top_prediction_risk: Optional[str] = None