from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal


# ─────────────────────────────────────────────
# SUPPLIER
# ─────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    phone: str = Field(..., min_length=10, max_length=15)
    address: Optional[str] = None
    gst_number: Optional[str] = None
    products_supplied: Optional[str] = None   # free-text description


class SupplierOut(BaseModel):
    supplier_id: int
    name: str
    phone: str
    address: Optional[str]
    gst_number: Optional[str]
    products_supplied: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# PURCHASE ORDER
# ─────────────────────────────────────────────

class POItemCreate(BaseModel):
    product_id: int
    quantity_ordered: int = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)


class POCreate(BaseModel):
    supplier_id: int
    items: List[POItemCreate]
    expected_date: Optional[date] = None


class POItemOut(BaseModel):
    po_item_id: int
    product_id: int
    product_name: str
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal

    class Config:
        from_attributes = True


class POOut(BaseModel):
    po_id: int
    supplier_id: int
    supplier_name: str
    status: str           # draft / sent / received / cancelled
    order_date: datetime
    expected_date: Optional[date]
    total_amount: Decimal
    items: List[POItemOut]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# RECEIVE STOCK (GRN)
# ─────────────────────────────────────────────

class ReceiveItemRequest(BaseModel):
    po_item_id: int
    quantity_received: int = Field(..., ge=0)


class POReceiveRequest(BaseModel):
    items: List[ReceiveItemRequest]


# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

class SupplierStats(BaseModel):
    total_suppliers: int
    pending_orders: int          # POs with status = sent
    this_month_purchase: Decimal # total amount of POs this month
    low_stock_alerts: int        # products below reorder level