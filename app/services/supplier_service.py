"""
Suppliers Service — Phase 6
Handles supplier CRUD, Purchase Order creation, and GRN (stock receive).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from fastapi import HTTPException, status

from app.models.supplier import Supplier, PurchaseOrder, PurchaseOrderItem
from app.models.product import Product, Inventory, InventoryHistory
from app.schemas.suppliers import (
    SupplierCreate, SupplierOut,
    POCreate, POOut, POItemOut,
    POReceiveRequest, SupplierStats,
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _supplier_to_out(s: Supplier) -> SupplierOut:
    return SupplierOut(
        supplier_id=s.supplier_id,
        name=s.name,
        phone=s.phone,
        address=s.address,
        gst_number=s.gst_number,
        products_supplied=None,
        created_at=s.created_at,
    )


def _po_to_out(po: PurchaseOrder) -> POOut:
    items = [
        POItemOut(
            po_item_id=i.po_item_id,
            product_id=i.product_id,
            product_name=i.product.name if i.product else "Unknown",
            quantity_ordered=i.quantity_ordered,
            quantity_received=i.quantity_received,
            unit_cost=i.unit_cost,
        )
        for i in po.items
    ]
    return POOut(
        po_id=po.po_id,
        supplier_id=po.supplier_id,
        supplier_name=po.supplier.name if po.supplier else "Unknown",
        status=po.status,
        order_date=po.order_date,
        expected_date=po.expected_date,
        total_amount=po.total_amount,
        items=items,
    )


# ─────────────────────────────────────────────
# SUPPLIER CRUD
# ─────────────────────────────────────────────

def list_suppliers(
    db: Session,
    store_id: int,
    search: Optional[str] = None,
) -> List[SupplierOut]:
    q = db.query(Supplier).filter(Supplier.store_id == store_id)
    if search:
        q = q.filter(
            Supplier.name.ilike(f"%{search}%") |
            Supplier.phone.ilike(f"%{search}%")
        )
    return [_supplier_to_out(s) for s in q.order_by(Supplier.name).all()]


def create_supplier(
    db: Session,
    store_id: int,
    data: SupplierCreate,
) -> SupplierOut:
    existing = db.query(Supplier).filter(
        Supplier.store_id == store_id,
        Supplier.phone == data.phone,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A supplier with phone {data.phone} already exists.",
        )

    supplier = Supplier(
        store_id=store_id,
        name=data.name,
        phone=data.phone,
        address=data.address,
        gst_number=data.gst_number,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return _supplier_to_out(supplier)


# ─────────────────────────────────────────────
# PURCHASE ORDER
# ─────────────────────────────────────────────

def create_po(
    db: Session,
    store_id: int,
    user_id: int,
    data: POCreate,
) -> POOut:
    supplier = db.query(Supplier).filter(
        Supplier.supplier_id == data.supplier_id,
        Supplier.store_id == store_id,
    ).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    if not data.items:
        raise HTTPException(status_code=400, detail="PO must have at least one item.")

    total = Decimal("0")
    po_items_data = []

    for item in data.items:
        product = db.query(Product).filter(
            Product.product_id == item.product_id,
            Product.store_id == store_id,
            Product.is_active == True,
        ).first()
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product ID {item.product_id} not found.",
            )
        line_total = item.unit_cost * item.quantity_ordered
        total += line_total
        po_items_data.append((product, item))

    po = PurchaseOrder(
        store_id=store_id,
        supplier_id=data.supplier_id,
        status="sent",
        expected_date=data.expected_date,
        total_amount=total.quantize(Decimal("0.01")),
        created_by=user_id,
    )
    db.add(po)
    db.flush()

    for product, item in po_items_data:
        po_item = PurchaseOrderItem(
            po_id=po.po_id,
            product_id=product.product_id,
            quantity_ordered=item.quantity_ordered,
            quantity_received=0,
            unit_cost=item.unit_cost,
        )
        db.add(po_item)

    db.commit()
    db.refresh(po)
    return _po_to_out(po)


def list_pos(
    db: Session,
    store_id: int,
    supplier_id: Optional[int] = None,
) -> List[POOut]:
    q = db.query(PurchaseOrder).filter(PurchaseOrder.store_id == store_id)
    if supplier_id:
        q = q.filter(PurchaseOrder.supplier_id == supplier_id)
    pos = q.order_by(PurchaseOrder.order_date.desc()).all()
    return [_po_to_out(po) for po in pos]


# ─────────────────────────────────────────────
# RECEIVE STOCK (GRN)
# ─────────────────────────────────────────────

def receive_po(
    db: Session,
    store_id: int,
    user_id: int,
    po_id: int,
    data: POReceiveRequest,
) -> POOut:
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_id == po_id,
        PurchaseOrder.store_id == store_id,
    ).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status == "received":
        raise HTTPException(status_code=400, detail="This PO has already been received.")

    received_map = {r.po_item_id: r.quantity_received for r in data.items}

    for po_item in po.items:
        qty = received_map.get(po_item.po_item_id, 0)
        if qty <= 0:
            continue

        po_item.quantity_received = qty

        # Increment inventory
        inv = po_item.product.inventory
        if inv:
            inv.current_stock += qty
            # Update cost price to latest supplier cost
            po_item.product.cost_price = po_item.unit_cost
        else:
            inv = Inventory(
                product_id=po_item.product_id,
                current_stock=qty,
            )
            db.add(inv)

        # Audit trail
        history = InventoryHistory(
            product_id=po_item.product_id,
            change_type="stock_in",
            quantity=qty,
            reference_type="purchase_order",
            reference_id=po.po_id,
            note=f"Received from PO #{po.po_id} — {po.supplier.name}",
            created_by=user_id,
        )
        db.add(history)

    po.status = "received"
    db.commit()
    db.refresh(po)
    return _po_to_out(po)


# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def get_stats(db: Session, store_id: int) -> SupplierStats:
    total_suppliers = db.query(Supplier).filter(Supplier.store_id == store_id).count()

    pending = db.query(PurchaseOrder).filter(
        PurchaseOrder.store_id == store_id,
        PurchaseOrder.status == "sent",
    ).count()

    now = datetime.now()
    month_purchase = db.query(func.sum(PurchaseOrder.total_amount)).filter(
        PurchaseOrder.store_id == store_id,
        extract("month", PurchaseOrder.order_date) == now.month,
        extract("year", PurchaseOrder.order_date) == now.year,
    ).scalar() or Decimal("0")

    products = db.query(Product).filter(
        Product.store_id == store_id,
        Product.is_active == True,
    ).all()
    low_stock = sum(
        1 for p in products
        if p.inventory and p.inventory.current_stock <= p.reorder_level
    )

    return SupplierStats(
        total_suppliers=total_suppliers,
        pending_orders=pending,
        this_month_purchase=Decimal(str(month_purchase)).quantize(Decimal("0.01")),
        low_stock_alerts=low_stock,
    )