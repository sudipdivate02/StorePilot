"""
Billing Service — Phase 4
The most important service in StorePilot.
Everything in create_sale() runs inside ONE database transaction.
If anything fails (stock issue, DB error), everything rolls back.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.product import Product, Inventory, InventoryHistory
from app.models.sale import Sale, SaleItem, Invoice
from app.models.customer import Customer, CreditLedger
from app.schemas.billing import SaleCreate, SaleOut, SaleItemOut, SaleListItem


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _generate_invoice_number(db: Session, store_id: int) -> str:
    """SP-{store_id}-{zero-padded count}  e.g. SP-4-00042"""
    count = db.query(Invoice).join(Sale).filter(Sale.store_id == store_id).count()
    return f"SP-{store_id}-{str(count + 1).zfill(5)}"


def _extract_gst(price_inclusive: Decimal, gst_rate: Decimal) -> Decimal:
    """
    Indian GST is tax-inclusive in MRP.
    GST amount = price * rate / (100 + rate)
    """
    if gst_rate == 0:
        return Decimal("0")
    return (price_inclusive * gst_rate / (100 + gst_rate)).quantize(Decimal("0.01"))


# ─────────────────────────────────────────────
# CREATE SALE  — the core transaction
# ─────────────────────────────────────────────

def create_sale(
    db: Session,
    store_id: int,
    cashier_id: int,
    data: SaleCreate,
) -> SaleOut:

    if not data.items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    discount = data.discount_amount or Decimal("0")

    # ── STEP 1: Validate every product and check stock ──────────────────────
    line_data = []   # will hold enriched item info for steps below

    for cart_item in data.items:
        product = db.query(Product).filter(
            Product.product_id == cart_item.product_id,
            Product.store_id == store_id,
            Product.is_active == True,
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product ID {cart_item.product_id} not found.",
            )

        inv = product.inventory
        if not inv or inv.current_stock < cart_item.quantity:
            available = inv.current_stock if inv else 0
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{product.name}' has only {available} units in stock. "
                       f"Requested: {cart_item.quantity}.",
            )

        line_total = product.selling_price * cart_item.quantity
        gst_amount = _extract_gst(product.selling_price, product.gst_rate) * cart_item.quantity

        line_data.append({
            "product": product,
            "inventory": inv,
            "quantity": cart_item.quantity,
            "unit_price": product.selling_price,
            "gst_rate": product.gst_rate,
            "line_total": line_total,
            "line_gst": gst_amount,
        })

    # ── STEP 2: Calculate totals ─────────────────────────────────────────────
    total_line = sum(d["line_total"] for d in line_data)
    total_gst  = sum(d["line_gst"]  for d in line_data)
    subtotal   = total_line - total_gst          # base price (ex-GST)
    total      = total_line - discount           # what customer pays

    # ── STEP 3: Insert Sale row ──────────────────────────────────────────────
    sale = Sale(
        store_id=store_id,
        customer_id=data.customer_id,
        cashier_id=cashier_id,
        payment_type=data.payment_type,
        subtotal=subtotal.quantize(Decimal("0.01")),
        gst_amount=total_gst.quantize(Decimal("0.01")),
        discount_amount=discount.quantize(Decimal("0.01")),
        total_amount=total.quantize(Decimal("0.01")),
    )
    db.add(sale)
    db.flush()   # get sale_id

    # ── STEP 4: Insert SaleItem rows + decrement stock ───────────────────────
    for d in line_data:
        sale_item = SaleItem(
            sale_id=sale.sale_id,
            product_id=d["product"].product_id,
            quantity=d["quantity"],
            unit_price=d["unit_price"],
            gst_rate=d["gst_rate"],
            discount=Decimal("0"),
            line_total=d["line_total"].quantize(Decimal("0.01")),
        )
        db.add(sale_item)

        # Decrement stock
        d["inventory"].current_stock -= d["quantity"]

        # Audit trail
        history = InventoryHistory(
            product_id=d["product"].product_id,
            change_type="stock_out",
            quantity=d["quantity"],
            reference_type="sale",
            reference_id=sale.sale_id,
            note=f"Sold via billing — invoice {sale.sale_id}",
            created_by=cashier_id,
        )
        db.add(history)

    # ── STEP 5: Credit (Udhar) path ──────────────────────────────────────────
    if data.payment_type == "udhar":
        if not data.customer_id:
            raise HTTPException(
                status_code=400,
                detail="Customer ID is required for Udhar (credit) sales.",
            )
        customer = db.query(Customer).filter(
            Customer.customer_id == data.customer_id,
            Customer.store_id == store_id,
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")

        new_balance = (customer.credit_balance or Decimal("0")) + total
        customer.credit_balance = new_balance.quantize(Decimal("0.01"))

        ledger = CreditLedger(
            customer_id=customer.customer_id,
            sale_id=sale.sale_id,
            transaction_type="credit_given",
            amount=total.quantize(Decimal("0.01")),
            balance_after=new_balance.quantize(Decimal("0.01")),
            note=f"Sale #{sale.sale_id} — {data.payment_type.upper()}",
        )
        db.add(ledger)

    # ── STEP 6: Create Invoice record ────────────────────────────────────────
    invoice_number = _generate_invoice_number(db, store_id)
    invoice = Invoice(
        sale_id=sale.sale_id,
        invoice_number=invoice_number,
        pdf_path=None,   # PDF generation is Phase 10 (Reports module)
    )
    db.add(invoice)

    # ── STEP 7: Commit everything at once ────────────────────────────────────
    db.commit()
    db.refresh(sale)

    # ── Build response ───────────────────────────────────────────────────────
    items_out = [
        SaleItemOut(
            product_id=d["product"].product_id,
            product_name=d["product"].name,
            quantity=d["quantity"],
            unit_price=d["unit_price"],
            gst_rate=d["gst_rate"],
            line_total=d["line_total"].quantize(Decimal("0.01")),
        )
        for d in line_data
    ]

    return SaleOut(
        sale_id=sale.sale_id,
        invoice_number=invoice_number,
        payment_type=sale.payment_type,
        subtotal=sale.subtotal,
        gst_amount=sale.gst_amount,
        discount_amount=sale.discount_amount,
        total_amount=sale.total_amount,
        items=items_out,
        sale_date=sale.sale_date,
        message=f"Sale complete! Invoice {invoice_number} generated.",
    )


# ─────────────────────────────────────────────
# LIST SALES  (sales history)
# ─────────────────────────────────────────────

def list_sales(
    db: Session,
    store_id: int,
    limit: int = 50,
) -> List[SaleListItem]:
    sales = (
        db.query(Sale)
        .filter(Sale.store_id == store_id)
        .order_by(Sale.sale_date.desc())
        .limit(limit)
        .all()
    )
    result = []
    for s in sales:
        item_count = sum(si.quantity for si in s.sale_items)
        result.append(SaleListItem(
            sale_id=s.sale_id,
            invoice_number=s.invoice.invoice_number if s.invoice else "—",
            payment_type=s.payment_type,
            total_amount=s.total_amount,
            item_count=item_count,
            sale_date=s.sale_date,
        ))
    return result