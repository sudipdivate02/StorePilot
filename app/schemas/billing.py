from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


# ─────────────────────────────────────────────
# REQUEST  (frontend → backend)
# ─────────────────────────────────────────────

class CartItem(BaseModel):
    """One product line in the cart"""
    product_id: int
    quantity: int = Field(..., gt=0)


class SaleCreate(BaseModel):
    """
    What billing.html sends when cashier clicks "Charge & print bill"
    payment_type: cash | upi | udhar
    customer_id: only needed for udhar (credit) sales
    """
    items: List[CartItem]
    payment_type: str = Field(..., pattern="^(cash|upi|udhar)$")
    customer_id: Optional[int] = None
    discount_amount: Optional[Decimal] = Decimal("0")


# ─────────────────────────────────────────────
# RESPONSE  (backend → frontend)
# ─────────────────────────────────────────────

class SaleItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    gst_rate: Decimal
    line_total: Decimal

    class Config:
        from_attributes = True


class SaleOut(BaseModel):
    """
    Returned after a successful sale — billing.html uses this to:
    - Show the invoice number in the bill header
    - Display the final total
    - Trigger invoice download
    """
    sale_id: int
    invoice_number: str
    payment_type: str
    subtotal: Decimal
    gst_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    items: List[SaleItemOut]
    sale_date: datetime
    message: str

    class Config:
        from_attributes = True


class SaleListItem(BaseModel):
    """Compact row for the sales history list"""
    sale_id: int
    invoice_number: str
    payment_type: str
    total_amount: Decimal
    item_count: int
    sale_date: datetime

    class Config:
        from_attributes = True