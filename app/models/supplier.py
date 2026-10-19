"""
Group D — Supply Chain
Tables: suppliers, purchase_orders, purchase_order_items
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric,
    DateTime, Date, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(Integer, primary_key=True, autoincrement=True)
    store_id    = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    name        = Column(String(200), nullable=False)
    phone       = Column(String(15), nullable=True)
    address     = Column(String(400), nullable=True)
    gst_number  = Column(String(20), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    store       = relationship("Store", back_populates="suppliers")
    orders      = relationship("PurchaseOrder", back_populates="supplier")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id          = Column(Integer, primary_key=True, autoincrement=True)
    store_id       = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    supplier_id    = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    status         = Column(
        Enum("draft", "sent", "received", "cancelled", name="po_status_enum"),
        default="draft"
    )
    order_date     = Column(DateTime, default=datetime.utcnow)
    expected_date  = Column(Date, nullable=True)
    total_amount   = Column(Numeric(12, 2), default=0.00)
    created_by     = Column(Integer, ForeignKey("users.user_id"), nullable=True)

    supplier       = relationship("Supplier", back_populates="orders")
    items          = relationship("PurchaseOrderItem", back_populates="order")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    po_item_id         = Column(Integer, primary_key=True, autoincrement=True)
    po_id              = Column(Integer, ForeignKey("purchase_orders.po_id"), nullable=False)
    product_id         = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity_ordered   = Column(Integer, nullable=False)
    quantity_received  = Column(Integer, default=0)
    unit_cost          = Column(Numeric(10, 2), nullable=False)

    order              = relationship("PurchaseOrder", back_populates="items")
    product            = relationship("Product")