"""
Inventory Router
All endpoints prefixed /api/v1 (set in main.py when including this router).

Endpoints (from blueprint Phase 3):
  GET    /products                      — list + search + filter
  POST   /products                      — create product
  GET    /products/barcode/{code}       — barcode lookup for billing
  PUT    /products/{id}                 — edit product
  POST   /inventory/stock-in            — receive stock
  GET    /inventory/low-stock           — products below reorder level
  GET    /inventory/expiring            — products expiring soon
  GET    /inventory/stats               — 4 stat cards for inventory.html header
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.schemas.inventory import (
    ProductCreate, ProductUpdate, ProductOut,
    StockInRequest, StockInResponse,
    InventoryStats, LowStockItem, ExpiringItem,
)
from app.services import inventory_service

router = APIRouter()


# ── LIST PRODUCTS ──────────────────────────────────────────────────────────────
@router.get("/products", response_model=List[ProductOut])
def list_products(
    search: Optional[str] = Query(None, description="Search by name or barcode"),
    category: Optional[str] = Query(None, description="grocery|dairy|snacks|personal|beverages"),
    filter: Optional[str] = Query(None, description="low_stock | expiring | all"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return inventory_service.list_products(
        db, store_id=current_user["store_id"],
        search=search, category=category, filter=filter,
    )


# ── CREATE PRODUCT ─────────────────────────────────────────────────────────────
@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return inventory_service.create_product(
        db, store_id=current_user["store_id"],
        user_id=current_user["user_id"], data=data,
    )


# ── BARCODE LOOKUP  (must come before /{id} to avoid routing conflict) ─────────
@router.get("/products/barcode/{barcode}", response_model=ProductOut)
def get_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return inventory_service.get_by_barcode(
        db, store_id=current_user["store_id"], barcode=barcode,
    )


# ── EDIT PRODUCT ───────────────────────────────────────────────────────────────
@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return inventory_service.update_product(
        db, store_id=current_user["store_id"],
        product_id=product_id, data=data,
    )


# ── STOCK-IN ───────────────────────────────────────────────────────────────────
@router.post("/inventory/stock-in", response_model=StockInResponse)
def stock_in(
    data: StockInRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return inventory_service.stock_in(
        db, store_id=current_user["store_id"],
        user_id=current_user["user_id"], data=data,
    )


# ── LOW STOCK ──────────────────────────────────────────────────────────────────
@router.get("/inventory/low-stock", response_model=List[LowStockItem])
def get_low_stock(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return inventory_service.get_low_stock(db, store_id=current_user["store_id"])


# ── EXPIRING SOON ──────────────────────────────────────────────────────────────
@router.get("/inventory/expiring", response_model=List[ExpiringItem])
def get_expiring(
    days: int = Query(30, description="Look-ahead window in days (7 | 14 | 30)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return inventory_service.get_expiring(db, store_id=current_user["store_id"], days=days)


# ── STATS (4 header cards on inventory.html) ───────────────────────────────────
@router.get("/inventory/stats", response_model=InventoryStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return inventory_service.get_stats(db, store_id=current_user["store_id"])