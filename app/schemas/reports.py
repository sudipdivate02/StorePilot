from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import date


class SalesRow(BaseModel):
    date: str
    bills: int
    items_sold: int
    revenue: Decimal
    gst_collected: Decimal


class SalesSummaryReport(BaseModel):
    period: str
    total_revenue: Decimal
    total_bills: int
    total_items: int
    total_gst: Decimal
    avg_bill_value: Decimal
    rows: List[SalesRow]


class ProfitRow(BaseModel):
    date: str
    revenue: Decimal
    cost: Decimal
    profit: Decimal
    margin_pct: float


class ProfitLossReport(BaseModel):
    period: str
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    avg_margin_pct: float
    rows: List[ProfitRow]


class GSTRow(BaseModel):
    gst_rate: str
    taxable_amount: Decimal
    cgst: Decimal
    sgst: Decimal
    total_gst: Decimal


class GSTReport(BaseModel):
    period: str
    total_taxable: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_gst: Decimal
    rows: List[GSTRow]


class TopProductRow(BaseModel):
    rank: int
    product_name: str
    category: str
    qty_sold: int
    revenue: Decimal


class TopProductsReport(BaseModel):
    period: str
    rows: List[TopProductRow]


class UdharRow(BaseModel):
    customer_name: str
    phone: str
    outstanding: Decimal
    status: str


class UdharReport(BaseModel):
    total_outstanding: Decimal
    total_customers: int
    rows: List[UdharRow]


class PurchaseRow(BaseModel):
    supplier_name: str
    po_id: int
    order_date: str
    status: str
    total_amount: Decimal


class PurchaseReport(BaseModel):
    period: str
    total_purchased: Decimal
    total_orders: int
    rows: List[PurchaseRow]