"""
Customers Router — Phase 5
Endpoints:
  GET  /api/v1/customers              — list + search
  POST /api/v1/customers              — create customer
  GET  /api/v1/customers/stats        — 4 stat cards
  GET  /api/v1/customers/{id}/ledger  — udhar ledger
  POST /api/v1/customers/{id}/payment — record payment received
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.customers import (
    CustomerCreate, CustomerOut,
    PaymentRequest, LedgerEntry, CustomerStats,
)
from app.services import customer_service as customers_service

router = APIRouter()


@router.get("/customers/stats", response_model=CustomerStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return customers_service.get_stats(db, store_id=current_user["store_id"])


@router.get("/customers", response_model=List[CustomerOut])
def list_customers(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return customers_service.list_customers(
        db, store_id=current_user["store_id"], search=search,
    )


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return customers_service.create_customer(
        db, store_id=current_user["store_id"], data=data,
    )


@router.get("/customers/{customer_id}/ledger", response_model=List[LedgerEntry])
def get_ledger(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return customers_service.get_ledger(
        db, store_id=current_user["store_id"], customer_id=customer_id,
    )


@router.post("/customers/{customer_id}/payment", response_model=CustomerOut)
def record_payment(
    customer_id: int,
    data: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return customers_service.record_payment(
        db, store_id=current_user["store_id"],
        customer_id=customer_id, data=data,
    )