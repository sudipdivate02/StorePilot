from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


# ─────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────

class ProductCreate(BaseModel):
    """Matches the Add Product panel fields in inventory.html"""
    name: str = Field(..., min_length=1, max_length=150)
    category: str = Field(..., description="grocery | dairy | snacks | personal | beverages")
    barcode: Optional[str] = None
    selling_price: Decimal = Field(..., ge=0, decimal_places=2)
    cost_price: Decimal = Field(..., ge=0, decimal_places=2)
    opening_stock: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=5, ge=0)
    gst_rate: Decimal = Field(default=5, description="0 | 5 | 12 | 18 | 28")
    expiry_date: Optional[date] = None
    unit: Optional[str] = "pcs"


class ProductUpdate(BaseModel):
    """All fields optional for partial updates via PUT /products/{id}"""
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    category: Optional[str] = None
    barcode: Optional[str] = None
    selling_price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    reorder_level: Optional[int] = Field(None, ge=0)
    gst_rate: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    unit: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    """
    What the inventory.html table renders per row:
    name, category, barcode, selling_price, cost_price,
    current_stock, reorder_level, gst_rate, expiry_date,
    stock_status (ok | low | out)
    """
    product_id: int
    name: str
    category: str
    barcode: Optional[str]
    selling_price: Decimal
    cost_price: Decimal
    gst_rate: Decimal
    unit: Optional[str]
    reorder_level: int
    current_stock: int
    expiry_date: Optional[date]
    stock_status: str          # "ok" | "low" | "out"
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# STOCK-IN  (receive stock from supplier)
# ─────────────────────────────────────────────

class StockInRequest(BaseModel):
    """
    POST /inventory/stock-in
    Called when a supplier delivers stock (or manual stock correction).
    """
    product_id: int
    quantity: int = Field(..., gt=0)
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    cost_price: Optional[Decimal] = Field(None, ge=0)  # update cost if price changed
    note: Optional[str] = None


class StockInResponse(BaseModel):
    product_id: int
    product_name: str
    quantity_added: int
    new_stock: int
    message: str


# ─────────────────────────────────────────────
# STATS  (header strip on inventory.html)
# ─────────────────────────────────────────────

class InventoryStats(BaseModel):
    """
    4 stat cards at the top of inventory.html:
    total_products, low_stock_count, expiring_soon_count, total_value
    """
    total_products: int
    low_stock_count: int
    expiring_soon_count: int       # expiring within 30 days
    total_inventory_value: Decimal  # sum(current_stock * cost_price)


# ─────────────────────────────────────────────
# LOW STOCK & EXPIRING SOON responses
# ─────────────────────────────────────────────

class LowStockItem(BaseModel):
    product_id: int
    name: str
    category: str
    current_stock: int
    reorder_level: int
    selling_price: Decimal

    class Config:
        from_attributes = True


class ExpiringItem(BaseModel):
    product_id: int
    name: str
    category: str
    current_stock: int
    expiry_date: date
    days_until_expiry: int

    class Config:
        from_attributes = True