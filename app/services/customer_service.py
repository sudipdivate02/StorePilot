"""
Customers Service — Phase 5
Handles customer CRUD, udhar ledger, and payment recording.
"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.customer import Customer, CreditLedger
from app.schemas.customers import (
    CustomerCreate, CustomerOut, PaymentRequest,
    LedgerEntry, CustomerStats,
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = name.strip().split()
    return "".join(p[0].upper() for p in parts[:2])


def _status(balance: Decimal) -> str:
    if balance <= 0:
        return "clear"
    return "due"


def _to_out(c: Customer) -> CustomerOut:
    balance = c.credit_balance or Decimal("0")
    return CustomerOut(
        customer_id=c.customer_id,
        name=c.name,
        phone=c.phone,
        credit_balance=balance,
        status=_status(balance),
        initials=_initials(c.name),
        created_at=c.created_at,
    )


# ─────────────────────────────────────────────
# LIST / SEARCH
# ─────────────────────────────────────────────

def list_customers(
    db: Session,
    store_id: int,
    search: Optional[str] = None,
) -> List[CustomerOut]:
    q = db.query(Customer).filter(Customer.store_id == store_id)
    if search:
        q = q.filter(
            Customer.name.ilike(f"%{search}%") |
            Customer.phone.ilike(f"%{search}%")
        )
    customers = q.order_by(Customer.name).all()
    return [_to_out(c) for c in customers]


# ─────────────────────────────────────────────
# CREATE CUSTOMER
# ─────────────────────────────────────────────

def create_customer(
    db: Session,
    store_id: int,
    data: CustomerCreate,
) -> CustomerOut:
    # Duplicate phone check within the same store
    existing = db.query(Customer).filter(
        Customer.store_id == store_id,
        Customer.phone == data.phone,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A customer with phone {data.phone} already exists.",
        )

    customer = Customer(
        store_id=store_id,
        name=data.name,
        phone=data.phone,
        credit_balance=data.initial_credit or Decimal("0"),
    )
    db.add(customer)
    db.flush()

    # If initial credit > 0, write it to the ledger
    if data.initial_credit and data.initial_credit > 0:
        ledger = CreditLedger(
            customer_id=customer.customer_id,
            sale_id=None,
            transaction_type="credit_given",
            amount=data.initial_credit,
            balance_after=data.initial_credit,
            note="Initial outstanding on customer creation",
        )
        db.add(ledger)

    db.commit()
    db.refresh(customer)
    return _to_out(customer)


# ─────────────────────────────────────────────
# RECORD PAYMENT
# ─────────────────────────────────────────────

def record_payment(
    db: Session,
    store_id: int,
    customer_id: int,
    data: PaymentRequest,
) -> CustomerOut:
    customer = db.query(Customer).filter(
        Customer.customer_id == customer_id,
        Customer.store_id == store_id,
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    balance = customer.credit_balance or Decimal("0")
    if data.amount > balance:
        raise HTTPException(
            status_code=400,
            detail=f"Payment ₹{data.amount} exceeds outstanding balance ₹{balance}.",
        )

    new_balance = (balance - data.amount).quantize(Decimal("0.01"))
    customer.credit_balance = new_balance

    ledger = CreditLedger(
        customer_id=customer.customer_id,
        sale_id=None,
        transaction_type="payment_received",
        amount=data.amount,
        balance_after=new_balance,
        note=data.note or f"Payment received: ₹{data.amount}",
    )
    db.add(ledger)
    db.commit()
    db.refresh(customer)
    return _to_out(customer)


# ─────────────────────────────────────────────
# LEDGER
# ─────────────────────────────────────────────

def get_ledger(
    db: Session,
    store_id: int,
    customer_id: int,
) -> List[LedgerEntry]:
    customer = db.query(Customer).filter(
        Customer.customer_id == customer_id,
        Customer.store_id == store_id,
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    entries = (
        db.query(CreditLedger)
        .filter(CreditLedger.customer_id == customer_id)
        .order_by(CreditLedger.created_at.desc())
        .all()
    )
    return [
        LedgerEntry(
            ledger_id=e.ledger_id,
            transaction_type=e.transaction_type,
            amount=e.amount,
            balance_after=e.balance_after,
            note=e.note,
            created_at=e.created_at,
        )
        for e in entries
    ]


# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def get_stats(db: Session, store_id: int) -> CustomerStats:
    customers = db.query(Customer).filter(Customer.store_id == store_id).all()
    total = len(customers)
    total_outstanding = Decimal("0")
    overdue = 0
    cleared = 0

    for c in customers:
        bal = c.credit_balance or Decimal("0")
        total_outstanding += bal
        if bal > 0:
            overdue += 1
        else:
            cleared += 1

    return CustomerStats(
        total_customers=total,
        total_outstanding=total_outstanding.quantize(Decimal("0.01")),
        overdue_count=overdue,
        cleared_count=cleared,
    )