"""
Dashboard Service — Phase 7
Single endpoint that aggregates real numbers from every module.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from app.models.product import Product, Inventory
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer
from app.models.supplier import PurchaseOrder
from app.schemas.dashboard import DashboardSummary, TopProduct


def get_summary(db: Session, store_id: int) -> DashboardSummary:
    today = date.today()
    yesterday = today - timedelta(days=1)

    # ── TODAY'S SALES ─────────────────────────────────────────────────────
    today_sales = db.query(
        func.coalesce(func.sum(Sale.total_amount), 0),
        func.count(Sale.sale_id),
    ).filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) == today,
    ).one()

    today_revenue = Decimal(str(today_sales[0]))
    bills_today = today_sales[1]
    avg_bill = (today_revenue / bills_today).quantize(Decimal("0.01")) if bills_today else Decimal("0")

    # ── YESTERDAY'S REVENUE ───────────────────────────────────────────────
    yest = db.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) == yesterday,
    ).scalar()
    yesterday_revenue = Decimal(str(yest))

    if yesterday_revenue > 0:
        change_pct = float(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100)
    else:
        change_pct = 100.0 if today_revenue > 0 else 0.0

    # ── ITEMS SOLD TODAY ──────────────────────────────────────────────────
    items_today = db.query(
        func.coalesce(func.sum(SaleItem.quantity), 0)
    ).join(Sale).filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) == today,
    ).scalar()
    items_sold_today = int(items_today or 0)

    # ── ESTIMATED PROFIT (revenue - cost of goods sold today) ─────────────
    cost_today = db.query(
        func.coalesce(func.sum(SaleItem.quantity * Product.cost_price), 0)
    ).join(Sale, Sale.sale_id == SaleItem.sale_id)\
     .join(Product, Product.product_id == SaleItem.product_id)\
     .filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) == today,
     ).scalar()
    estimated_profit = (today_revenue - Decimal(str(cost_today))).quantize(Decimal("0.01"))

    # ── WEEKLY REVENUE (last 7 days) ──────────────────────────────────────
    weekly_revenue = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        rev = db.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(
            Sale.store_id == store_id,
            func.date(Sale.sale_date) == day,
        ).scalar()
        weekly_revenue.append(float(rev or 0))

    # ── LOW STOCK ─────────────────────────────────────────────────────────
    products = db.query(Product).filter(
        Product.store_id == store_id,
        Product.is_active == True,
    ).all()

    low_stock_items = []
    expiring_items = []
    cutoff = today + timedelta(days=30)

    for p in products:
        stock = p.inventory.current_stock if p.inventory else 0
        if stock <= p.reorder_level:
            low_stock_items.append(p.name)
        exp = p.inventory.expiry_date if p.inventory else None
        if exp and today <= exp <= cutoff:
            expiring_items.append(p.name)

    # ── UDHAR ─────────────────────────────────────────────────────────────
    customers = db.query(Customer).filter(Customer.store_id == store_id).all()
    udhar_total = sum((c.credit_balance or Decimal("0")) for c in customers)
    udhar_count = sum(1 for c in customers if (c.credit_balance or 0) > 0)

    # ── OPEN POs ──────────────────────────────────────────────────────────
    open_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.store_id == store_id,
        PurchaseOrder.status == "sent",
    ).count()

    # ── TOP PRODUCTS TODAY ────────────────────────────────────────────────
    top_rows = db.query(
        Product.product_id,
        Product.name,
        func.sum(SaleItem.quantity).label("qty_sold"),
    ).join(SaleItem, SaleItem.product_id == Product.product_id)\
     .join(Sale, Sale.sale_id == SaleItem.sale_id)\
     .filter(
        Sale.store_id == store_id,
        func.date(Sale.sale_date) == today,
     ).group_by(Product.product_id, Product.name)\
      .order_by(func.sum(SaleItem.quantity).desc())\
      .limit(5).all()

    max_qty = top_rows[0][2] if top_rows else 1
    top_products = [
        TopProduct(
            product_id=row[0],
            name=row[1],
            qty_sold=int(row[2]),
            pct=int((row[2] / max_qty) * 100),
        )
        for row in top_rows
    ]

    # ── OLDEST UDHAR (days) ───────────────────────────────────────────────
    oldest_days = 0
    if udhar_count > 0:
        from app.models.customer import CreditLedger
        oldest = db.query(func.min(CreditLedger.created_at))\
            .join(Customer)\
            .filter(
                Customer.store_id == store_id,
                CreditLedger.transaction_type == "credit_given",
            ).scalar()
        if oldest:
            oldest_days = (datetime.now() - oldest).days

    # ── UDHAR CUSTOMERS (top 4 with outstanding) ──────────────────────────
    def _initials(name):
        parts = name.strip().split()
        return "".join(p[0].upper() for p in parts[:2])

    from app.schemas.dashboard import UdharCustomer
    udhar_customers_raw = sorted(
        [c for c in customers if (c.credit_balance or 0) > 0],
        key=lambda x: x.credit_balance, reverse=True
    )[:4]
    udhar_customers_out = [
        UdharCustomer(name=c.name, initials=_initials(c.name),
                      credit_balance=c.credit_balance or Decimal("0"))
        for c in udhar_customers_raw
    ]

    # ── TOP PREDICTION (highest-risk product) ─────────────────────────────
    top_pred_name = top_pred_range = top_pred_reason = top_pred_risk = None
    try:
        from app.services.prediction_service import get_all_predictions
        preds = get_all_predictions(db, store_id)
        if preds.ready:
            top = preds.ready[0]
            top_pred_name = top.product_name
            top_pred_range = f"{top.confidence_low}-{top.confidence_high} units"
            top_pred_reason = top.reason
            top_pred_risk = top.risk_level
    except Exception:
        pass

    return DashboardSummary(
        today_revenue=today_revenue,
        yesterday_revenue=yesterday_revenue,
        revenue_change_pct=round(change_pct, 1),
        bills_today=bills_today,
        avg_bill_value=avg_bill,
        items_sold_today=items_sold_today,
        weekly_revenue=weekly_revenue,
        estimated_profit=estimated_profit,
        low_stock_count=len(low_stock_items),
        low_stock_items=low_stock_items[:3],
        expiring_count=len(expiring_items),
        expiring_items=expiring_items[:2],
        pending_udhar=Decimal(str(udhar_total)).quantize(Decimal("0.01")),
        udhar_customer_count=udhar_count,
        open_pos=open_pos,
        top_products=top_products,
        udhar_total=Decimal(str(udhar_total)).quantize(Decimal("0.01")),
        udhar_oldest_days=oldest_days,
        udhar_customers=udhar_customers_out,
        top_prediction_name=top_pred_name,
        top_prediction_range=top_pred_range,
        top_prediction_reason=top_pred_reason,
        top_prediction_risk=top_pred_risk,
    )