"""
Notification Service — Phase 9
Sweep job checks all triggers and writes to notifications table.
Duplicate check: if same type + same message already unread, skip.
"""

from datetime import date, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.system import Notification
from app.models.product import Product
from app.models.customer import Customer
from app.models.supplier import PurchaseOrder
from app.schemas.notifications import NotificationOut, NotificationsListOut


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _already_unread(db: Session, store_id: int, ntype: str, message: str) -> bool:
    """Avoid duplicate spam — skip if same type + message already unread."""
    existing = db.query(Notification).filter(
        Notification.store_id == store_id,
        Notification.type == ntype,
        Notification.message == message,
        Notification.is_read == False,
    ).first()
    return existing is not None


def _add(db: Session, store_id: int, ntype: str, message: str):
    if not _already_unread(db, store_id, ntype, message):
        db.add(Notification(
            store_id=store_id,
            type=ntype,
            message=message,
            is_read=False,
        ))


# ─────────────────────────────────────────────
# SWEEP JOB — called by APScheduler
# ─────────────────────────────────────────────

def run_sweep(db: Session, store_id: int):
    """
    Evaluates all 4 trigger types and writes notifications.
    Called daily by APScheduler; also callable manually via POST /notifications/sweep.
    """
    today = date.today()
    cutoff_30 = today + timedelta(days=30)
    cutoff_7  = today + timedelta(days=7)

    products = db.query(Product).filter(
        Product.store_id == store_id,
        Product.is_active == True,
    ).all()

    # ── LOW STOCK ──────────────────────────────────────────────────────────
    low = [p for p in products if p.inventory and p.inventory.current_stock <= p.reorder_level]
    if low:
        names = ", ".join(p.name for p in low[:3])
        suffix = f" and {len(low) - 3} more" if len(low) > 3 else ""
        _add(db, store_id, "low_stock",
             f"{len(low)} items running low — {names}{suffix}. Consider reordering.")

    # ── EXPIRY ─────────────────────────────────────────────────────────────
    expiring_7  = [p for p in products
                   if p.inventory and p.inventory.expiry_date
                   and today <= p.inventory.expiry_date <= cutoff_7]
    expiring_30 = [p for p in products
                   if p.inventory and p.inventory.expiry_date
                   and cutoff_7 < p.inventory.expiry_date <= cutoff_30]

    for p in expiring_7:
        days = (p.inventory.expiry_date - today).days
        _add(db, store_id, "expiry",
             f"{p.name} expires in {days} day{'s' if days != 1 else ''}. "
             f"{p.inventory.current_stock} units remaining — consider discounting.")

    if expiring_30:
        names = ", ".join(p.name for p in expiring_30[:3])
        _add(db, store_id, "expiry",
             f"{len(expiring_30)} item(s) expiring this month — {names}.")

    # ── CREDIT DUE ─────────────────────────────────────────────────────────
    customers = db.query(Customer).filter(
        Customer.store_id == store_id,
        Customer.credit_balance > 0,
    ).all()
    if customers:
        from decimal import Decimal
        total = sum(c.credit_balance or Decimal("0") for c in customers)
        names = ", ".join(c.name for c in customers[:3])
        suffix = f" and {len(customers) - 3} more" if len(customers) > 3 else ""
        _add(db, store_id, "credit_due",
             f"\u20B9{int(total)} outstanding from {len(customers)} customer(s) — {names}{suffix}.")

    # ── OPEN PURCHASE ORDERS ───────────────────────────────────────────────
    open_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.store_id == store_id,
        PurchaseOrder.status == "sent",
    ).all()
    if open_pos:
        supplier_names = list({po.supplier.name for po in open_pos if po.supplier})[:3]
        _add(db, store_id, "open_po",
             f"{len(open_pos)} purchase order(s) awaiting delivery from "
             f"{', '.join(supplier_names)}.")

    db.commit()


# ─────────────────────────────────────────────
# GET NOTIFICATIONS
# ─────────────────────────────────────────────

def get_notifications(db: Session, store_id: int, unread_only: bool = False) -> NotificationsListOut:
    q = db.query(Notification).filter(Notification.store_id == store_id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    notifications = q.order_by(Notification.created_at.desc()).limit(50).all()
    unread_count = db.query(Notification).filter(
        Notification.store_id == store_id,
        Notification.is_read == False,
    ).count()
    return NotificationsListOut(
        unread_count=unread_count,
        notifications=[NotificationOut(
            notification_id=n.notification_id,
            type=n.type,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at,
        ) for n in notifications],
    )


# ─────────────────────────────────────────────
# MARK AS READ
# ─────────────────────────────────────────────

def mark_read(db: Session, store_id: int, notification_id: int):
    n = db.query(Notification).filter(
        Notification.notification_id == notification_id,
        Notification.store_id == store_id,
    ).first()
    if n:
        n.is_read = True
        db.commit()
    return {"message": "Marked as read"}


def mark_all_read(db: Session, store_id: int):
    db.query(Notification).filter(
        Notification.store_id == store_id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}