"""
Billing Router — Phase 4
Endpoints:
  POST  /api/v1/sales         — create sale (charge button)
  GET   /api/v1/sales         — sales history
  GET   /api/v1/sales/{id}    — single sale detail
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.billing import SaleCreate, SaleOut, SaleListItem
from app.services import billing_service

router = APIRouter()


@router.post("/sales", response_model=SaleOut, status_code=201)
def create_sale(
    data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return billing_service.create_sale(
        db=db,
        store_id=current_user["store_id"],
        cashier_id=current_user["user_id"],
        data=data,
    )


@router.get("/sales", response_model=List[SaleListItem])
def list_sales(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return billing_service.list_sales(
        db=db,
        store_id=current_user["store_id"],
        limit=limit,
    )