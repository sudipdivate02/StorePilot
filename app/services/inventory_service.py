"""
Inventory Service
All business logic for products, stock movements, low-stock checks, expiry checks.
Routers call these functions; they never touch the DB directly.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.product import Product, Inventory, InventoryHistory, Category
from app.schemas.inventory import (
    ProductCreate, ProductUpdate, ProductOut,
    StockInRequest, StockInResponse,
    InventoryStats, LowStockItem, ExpiringItem,
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _stock_status(current: int, reorder: int) -> str:
    if current <= 0:
        return "out"
    if current <= reorder:
        return "low"
    return "ok"


def _product_to_out(product: Product) -> ProductOut:
    stock = product.inventory.current_stock if product.inventory else 0
    expiry = product.inventory.expiry_date if product.inventory else None
    # Return the human-readable category name, not the integer FK
    category_name = product.category.category_name if product.category else "grocery"
    return ProductOut(
        product_id=product.product_id,
        name=product.name,
        category=category_name,
        barcode=product.barcode,
        selling_price=product.selling_price,
        cost_price=product.cost_price,
        gst_rate=product.gst_rate,
        unit=product.unit,
        reorder_level=product.reorder_level,
        current_stock=stock,
        expiry_date=expiry,
        stock_status=_stock_status(stock, product.reorder_level),
        is_active=product.is_active,
        created_at=product.created_at,
    )


# ─────────────────────────────────────────────
# LIST PRODUCTS
# ─────────────────────────────────────────────

def list_products(
    db: Session,
    store_id: int,
    search: Optional[str] = None,
    category: Optional[str] = None,
    filter: Optional[str] = None,
) -> List[ProductOut]:
    q = (
        db.query(Product)
        .filter(Product.store_id == store_id, Product.is_active == True)
    )

    if search:
        q = q.filter(
            Product.name.ilike(f"%{search}%") |
            Product.barcode.ilike(f"%{search}%")
        )

    if category and category != "all":
        # Join Category and filter by name string
        q = q.join(Category, Product.category_id == Category.category_id)\
             .filter(Category.category_name == category)

    products = q.order_by(Product.name).all()

    if filter == "low_stock":
        products = [
            p for p in products
            if p.inventory and p.inventory.current_stock <= p.reorder_level
        ]
    elif filter == "expiring":
        cutoff = date.today() + timedelta(days=30)
        products = [
            p for p in products
            if p.inventory and p.inventory.expiry_date and p.inventory.expiry_date <= cutoff
        ]

    return [_product_to_out(p) for p in products]


# ─────────────────────────────────────────────
# CREATE PRODUCT
# ─────────────────────────────────────────────

def create_product(
    db: Session,
    store_id: int,
    user_id: int,
    data: ProductCreate,
) -> ProductOut:
    # Duplicate barcode check
    if data.barcode:
        existing = db.query(Product).filter(
            Product.store_id == store_id,
            Product.barcode == data.barcode,
            Product.is_active == True,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Barcode {data.barcode} is already assigned to '{existing.name}'.",
            )

    # Resolve category name → integer category_id
    # Auto-create the category row if it doesn't exist yet
    category = db.query(Category).filter(
        Category.store_id == store_id,
        Category.category_name == data.category,
    ).first()
    if not category:
        category = Category(
            store_id=store_id,
            category_name=data.category,
        )
        db.add(category)
        db.flush()   # get category_id immediately

    product = Product(
        store_id=store_id,
        category_id=category.category_id,   # ← integer, not the string
        name=data.name,
        barcode=data.barcode,
        unit=data.unit or "pcs",
        cost_price=data.cost_price,
        selling_price=data.selling_price,
        gst_rate=data.gst_rate,
        reorder_level=data.reorder_level,
        expiry_tracked=bool(data.expiry_date),
        is_active=True,
    )
    db.add(product)
    db.flush()   # get product_id without committing

    # Create inventory row
    inv = Inventory(
        product_id=product.product_id,
        current_stock=data.opening_stock,
        expiry_date=data.expiry_date,
    )
    db.add(inv)

    # Write opening stock to history if > 0
    if data.opening_stock > 0:
        history = InventoryHistory(
            product_id=product.product_id,
            change_type="stock_in",
            quantity=data.opening_stock,
            reference_type="opening_stock",
            note="Opening stock on product creation",
            created_by=user_id,
        )
        db.add(history)

    db.commit()
    db.refresh(product)
    return _product_to_out(product)


# ─────────────────────────────────────────────
# BARCODE LOOKUP  (used by billing.html scan)
# ─────────────────────────────────────────────

def get_by_barcode(db: Session, store_id: int, barcode: str) -> ProductOut:
    product = db.query(Product).filter(
        Product.store_id == store_id,
        Product.barcode == barcode,
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product found with barcode '{barcode}'.",
        )
    return _product_to_out(product)


# ─────────────────────────────────────────────
# UPDATE PRODUCT
# ─────────────────────────────────────────────

def update_product(
    db: Session,
    store_id: int,
    product_id: int,
    data: ProductUpdate,
) -> ProductOut:
    product = db.query(Product).filter(
        Product.product_id == product_id,
        Product.store_id == store_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "category":
            setattr(product, "category_id", value)
        else:
            setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return _product_to_out(product)


# ─────────────────────────────────────────────
# STOCK-IN  (receive goods)
# ─────────────────────────────────────────────

def stock_in(
    db: Session,
    store_id: int,
    user_id: int,
    data: StockInRequest,
) -> StockInResponse:
    product = db.query(Product).filter(
        Product.product_id == data.product_id,
        Product.store_id == store_id,
        Product.is_active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    inv = product.inventory
    if not inv:
        raise HTTPException(status_code=500, detail="Inventory record missing for product.")

    # Update stock
    inv.current_stock += data.quantity

    # Update batch/expiry if provided
    if data.batch_number:
        inv.batch_number = data.batch_number
    if data.expiry_date:
        inv.expiry_date = data.expiry_date

    # Update cost price if supplier price changed
    if data.cost_price is not None:
        product.cost_price = data.cost_price

    # Write to history
    history = InventoryHistory(
        product_id=product.product_id,
        change_type="stock_in",
        quantity=data.quantity,
        reference_type="manual_stock_in",
        note=data.note or f"Stock received: +{data.quantity} units",
        created_by=user_id,
    )
    db.add(history)
    db.commit()

    return StockInResponse(
        product_id=product.product_id,
        product_name=product.name,
        quantity_added=data.quantity,
        new_stock=inv.current_stock,
        message=f"Stock updated. {product.name} now has {inv.current_stock} units.",
    )


# ─────────────────────────────────────────────
# STATS  (4 cards in inventory.html header)
# ─────────────────────────────────────────────

def get_stats(db: Session, store_id: int) -> InventoryStats:
    products = (
        db.query(Product)
        .filter(Product.store_id == store_id, Product.is_active == True)
        .all()
    )

    total = len(products)
    low_stock = 0
    expiring = 0
    total_value = Decimal("0")
    cutoff = date.today() + timedelta(days=30)

    for p in products:
        stock = p.inventory.current_stock if p.inventory else 0
        if stock <= p.reorder_level:
            low_stock += 1
        exp = p.inventory.expiry_date if p.inventory else None
        if exp and exp <= cutoff:
            expiring += 1
        total_value += Decimal(str(stock)) * p.cost_price

    return InventoryStats(
        total_products=total,
        low_stock_count=low_stock,
        expiring_soon_count=expiring,
        total_inventory_value=total_value.quantize(Decimal("0.01")),
    )


# ─────────────────────────────────────────────
# LOW STOCK LIST
# ─────────────────────────────────────────────

def get_low_stock(db: Session, store_id: int) -> List[LowStockItem]:
    products = (
        db.query(Product)
        .filter(Product.store_id == store_id, Product.is_active == True)
        .all()
    )
    result = []
    for p in products:
        stock = p.inventory.current_stock if p.inventory else 0
        if stock <= p.reorder_level:
            result.append(LowStockItem(
                product_id=p.product_id,
                name=p.name,
                category=p.category.category_name if p.category else "grocery",
                current_stock=stock,
                reorder_level=p.reorder_level,
                selling_price=p.selling_price,
            ))
    return result


# ─────────────────────────────────────────────
# EXPIRING SOON LIST
# ─────────────────────────────────────────────

def get_expiring(db: Session, store_id: int, days: int = 30) -> List[ExpiringItem]:
    cutoff = date.today() + timedelta(days=days)
    today = date.today()

    products = (
        db.query(Product)
        .filter(Product.store_id == store_id, Product.is_active == True, Product.expiry_tracked == True)
        .all()
    )
    result = []
    for p in products:
        exp = p.inventory.expiry_date if p.inventory else None
        if exp and today <= exp <= cutoff:
            result.append(ExpiringItem(
                product_id=p.product_id,
                name=p.name,
                category=p.category.category_name if p.category else "grocery",
                current_stock=p.inventory.current_stock,
                expiry_date=exp,
                days_until_expiry=(exp - today).days,
            ))

    # Sort soonest first
    result.sort(key=lambda x: x.days_until_expiry)
    return result