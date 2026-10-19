"""
Reports Service — Phase 10
All 6 reports as JSON (no PDF deps). Frontend renders and offers CSV download.
Default period: current calendar month.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer
from app.models.supplier import PurchaseOrder

from app.schemas.reports import (
    SalesSummaryReport, SalesRow,
    ProfitLossReport, ProfitRow,
    GSTReport, GSTRow,
    TopProductsReport, TopProductRow,
    UdharReport, UdharRow,
    PurchaseReport, PurchaseRow,
)


def _period_bounds(months_back: int = 0):
    today = date.today()
    year = today.year
    month = today.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    label = start.strftime("%B %Y")
    return start, end, label


# ─────────────────────────────────────────────
# 1. SALES SUMMARY
# ─────────────────────────────────────────────

def sales_summary(db: Session, store_id: int, months_back: int = 0) -> SalesSummaryReport:
    start, end, label = _period_bounds(months_back)

    sales = db.query(Sale).filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
    ).all()

    by_date = {}
    for s in sales:
        d = s.sale_date.date().isoformat()
        if d not in by_date:
            by_date[d] = {"bills": 0, "items": 0, "revenue": Decimal("0"), "gst": Decimal("0")}
        by_date[d]["bills"] += 1
        by_date[d]["items"] += sum(i.quantity for i in s.sale_items)
        by_date[d]["revenue"] += s.total_amount
        by_date[d]["gst"] += s.gst_amount

    rows = [
        SalesRow(
            date=d,
            bills=v["bills"],
            items_sold=v["items"],
            revenue=v["revenue"],
            gst_collected=v["gst"],
        )
        for d, v in sorted(by_date.items())
    ]

    total_rev = sum(r.revenue for r in rows) or Decimal("0")
    total_bills = sum(r.bills for r in rows)
    total_items = sum(r.items_sold for r in rows)
    total_gst = sum(r.gst_collected for r in rows) or Decimal("0")

    return SalesSummaryReport(
        period=label,
        total_revenue=total_rev,
        total_bills=total_bills,
        total_items=total_items,
        total_gst=total_gst,
        avg_bill_value=(total_rev / total_bills).quantize(Decimal("0.01")) if total_bills else Decimal("0"),
        rows=rows,
    )


# ─────────────────────────────────────────────
# 2. PROFIT & LOSS
# ─────────────────────────────────────────────

def profit_loss(db: Session, store_id: int, months_back: int = 0) -> ProfitLossReport:
    start, end, label = _period_bounds(months_back)

    sales = db.query(Sale).filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
    ).all()

    by_date = {}
    for s in sales:
        d = s.sale_date.date().isoformat()
        cost = sum(
            (i.product.cost_price if i.product else Decimal("0")) * i.quantity
            for i in s.sale_items
        )
        if d not in by_date:
            by_date[d] = {"revenue": Decimal("0"), "cost": Decimal("0")}
        by_date[d]["revenue"] += s.total_amount
        by_date[d]["cost"] += cost

    rows = []
    for d, v in sorted(by_date.items()):
        profit = v["revenue"] - v["cost"]
        margin = float((profit / v["revenue"]) * 100) if v["revenue"] else 0.0
        rows.append(ProfitRow(
            date=d,
            revenue=v["revenue"],
            cost=v["cost"].quantize(Decimal("0.01")),
            profit=profit.quantize(Decimal("0.01")),
            margin_pct=round(margin, 1),
        ))

    total_rev = sum(r.revenue for r in rows) or Decimal("0")
    total_cost = sum(r.cost for r in rows) or Decimal("0")
    total_profit = total_rev - total_cost
    avg_margin = float((total_profit / total_rev) * 100) if total_rev else 0.0

    return ProfitLossReport(
        period=label,
        total_revenue=total_rev,
        total_cost=total_cost.quantize(Decimal("0.01")),
        total_profit=total_profit.quantize(Decimal("0.01")),
        avg_margin_pct=round(avg_margin, 1),
        rows=rows,
    )


# ─────────────────────────────────────────────
# 3. GST REPORT
# ─────────────────────────────────────────────

def gst_report(db: Session, store_id: int, months_back: int = 0) -> GSTReport:
    start, end, label = _period_bounds(months_back)

    items = db.query(SaleItem).join(Sale).filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
    ).all()

    by_rate = {}
    for item in items:
        rate = str(item.gst_rate)
        if rate not in by_rate:
            by_rate[rate] = {"taxable": Decimal("0"), "gst": Decimal("0")}
        total = item.line_total
        gst = (total * item.gst_rate / (100 + item.gst_rate)).quantize(Decimal("0.01"))
        taxable = (total - gst).quantize(Decimal("0.01"))
        by_rate[rate]["taxable"] += taxable
        by_rate[rate]["gst"] += gst

    rows = [
        GSTRow(
            gst_rate=f"{r}%",
            taxable_amount=v["taxable"],
            cgst=(v["gst"] / 2).quantize(Decimal("0.01")),
            sgst=(v["gst"] / 2).quantize(Decimal("0.01")),
            total_gst=v["gst"],
        )
        for r, v in sorted(by_rate.items())
    ]

    total_taxable = sum(r.taxable_amount for r in rows) or Decimal("0")
    total_gst = sum(r.total_gst for r in rows) or Decimal("0")

    return GSTReport(
        period=label,
        total_taxable=total_taxable,
        total_cgst=(total_gst / 2).quantize(Decimal("0.01")),
        total_sgst=(total_gst / 2).quantize(Decimal("0.01")),
        total_gst=total_gst,
        rows=rows,
    )


# ─────────────────────────────────────────────
# 4. TOP PRODUCTS
# ─────────────────────────────────────────────

def top_products(db: Session, store_id: int, months_back: int = 0) -> TopProductsReport:
    start, end, label = _period_bounds(months_back)

    rows_raw = db.query(
        Product.product_id,
        Product.name,
        func.sum(SaleItem.quantity).label("qty"),
        func.sum(SaleItem.line_total).label("revenue"),
    ).join(SaleItem, SaleItem.product_id == Product.product_id)\
     .join(Sale, Sale.sale_id == SaleItem.sale_id)\
     .filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
     ).group_by(Product.product_id, Product.name)\
      .order_by(func.sum(SaleItem.quantity).desc())\
      .limit(20).all()

    rows = [
        TopProductRow(
            rank=i + 1,
            product_name=r[1],
            category="—",
            qty_sold=int(r[2]),
            revenue=Decimal(str(r[3])).quantize(Decimal("0.01")),
        )
        for i, r in enumerate(rows_raw)
    ]

    return TopProductsReport(period=label, rows=rows)


# ─────────────────────────────────────────────
# 5. UDHAR REPORT
# ─────────────────────────────────────────────

def udhar_report(db: Session, store_id: int) -> UdharReport:
    customers = db.query(Customer).filter(Customer.store_id == store_id).all()
    rows = []
    total = Decimal("0")

    for c in sorted(customers, key=lambda x: x.credit_balance or 0, reverse=True):
        bal = c.credit_balance or Decimal("0")
        total += bal
        rows.append(UdharRow(
            customer_name=c.name,
            phone=c.phone or "—",
            outstanding=bal,
            status="clear" if bal <= 0 else "due",
        ))

    return UdharReport(
        total_outstanding=total.quantize(Decimal("0.01")),
        total_customers=len(rows),
        rows=rows,
    )


# ─────────────────────────────────────────────
# 6. PURCHASE REPORT
# ─────────────────────────────────────────────

def purchase_report(db: Session, store_id: int, months_back: int = 0) -> PurchaseReport:
    start, end, label = _period_bounds(months_back)

    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.store_id == store_id,
        func.date(PurchaseOrder.order_date) >= start,
        func.date(PurchaseOrder.order_date) <= end,
    ).order_by(PurchaseOrder.order_date.desc()).all()

    rows = [
        PurchaseRow(
            supplier_name=po.supplier.name if po.supplier else "—",
            po_id=po.po_id,
            order_date=po.order_date.date().isoformat(),
            status=po.status,
            total_amount=po.total_amount,
        )
        for po in pos
    ]

    total = sum(r.total_amount for r in rows) or Decimal("0")

    return PurchaseReport(
        period=label,
        total_purchased=total.quantize(Decimal("0.01")),
        total_orders=len(rows),
        rows=rows,
    )