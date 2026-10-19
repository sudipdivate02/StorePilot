"""
Suppliers Router — Phase 6
Endpoints:
  GET  /api/v1/suppliers                    — list suppliers
  POST /api/v1/suppliers                    — create supplier
  GET  /api/v1/suppliers/stats              — 4 stat cards
  GET  /api/v1/purchase-orders              — list all POs
  POST /api/v1/purchase-orders              — create PO
  POST /api/v1/purchase-orders/{id}/receive — receive stock (GRN)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.schemas.suppliers import (
    SupplierCreate, SupplierOut,
    POCreate, POOut,
    POReceiveRequest, SupplierStats,
)
from app.services import supplier_service

router = APIRouter()


@router.get("/suppliers/stats", response_model=SupplierStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return supplier_service.get_stats(db, store_id=current_user["store_id"])


@router.get("/suppliers", response_model=List[SupplierOut])
def list_suppliers(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return supplier_service.list_suppliers(
        db, store_id=current_user["store_id"], search=search,
    )


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return supplier_service.create_supplier(
        db, store_id=current_user["store_id"], data=data,
    )


@router.get("/purchase-orders", response_model=List[POOut])
def list_pos(
    supplier_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return supplier_service.list_pos(
        db, store_id=current_user["store_id"], supplier_id=supplier_id,
    )


@router.post("/purchase-orders", response_model=POOut, status_code=201)
def create_po(
    data: POCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return supplier_service.create_po(
        db,
        store_id=current_user["store_id"],
        user_id=current_user["user_id"],
        data=data,
    )


@router.post("/purchase-orders/{po_id}/receive", response_model=POOut)
def receive_po(
    po_id: int,
    data: POReceiveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return supplier_service.receive_po(
        db,
        store_id=current_user["store_id"],
        user_id=current_user["user_id"],
        po_id=po_id,
        data=data,
    )