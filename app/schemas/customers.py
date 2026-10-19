from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# ─────────────────────────────────────────────
# REQUEST
# ─────────────────────────────────────────────

class CustomerCreate(BaseModel):
    """Matches the Add Customer panel fields in customers.html"""
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    initial_credit: Optional[Decimal] = Decimal("0")


class PaymentRequest(BaseModel):
    """POST /customers/{id}/payment — record money received from customer"""
    amount: Decimal = Field(..., gt=0)
    note: Optional[str] = None


# ─────────────────────────────────────────────
# RESPONSE
# ─────────────────────────────────────────────

class CustomerOut(BaseModel):
    """One customer card in the grid"""
    customer_id: int
    name: str
    phone: str
    credit_balance: Decimal      # outstanding udhar amount
    status: str                  # "clear" | "due" | "overdue"
    initials: str                # e.g. "PK" for Priya Kale
    created_at: datetime

    class Config:
        from_attributes = True


class LedgerEntry(BaseModel):
    """One row in the udhar ledger"""
    ledger_id: int
    transaction_type: str        # credit_given | payment_received
    amount: Decimal
    balance_after: Decimal
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerStats(BaseModel):
    """4 stat cards at the top of customers.html"""
    total_customers: int
    total_outstanding: Decimal   # sum of all credit_balance
    overdue_count: int           # customers with balance > 0 (due)
    cleared_count: int           # customers with balance = 0