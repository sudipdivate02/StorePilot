"""
Group C — Sales & Finance (sale side)
Tables: sales, sale_items, invoices
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric,
    DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base


class Sale(Base):
    __tablename__ = "sales"

    sale_id         = Column(Integer, primary_key=True, autoincrement=True)
    store_id        = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    customer_id     = Column(Integer, ForeignKey("customers.customer_id"), nullable=True)
    cashier_id      = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    sale_date       = Column(DateTime, default=datetime.utcnow)
    payment_type    = Column(String(10), nullable=False,default="cash")
    subtotal        = Column(Numeric(12, 2), nullable=False)
    gst_amount      = Column(Numeric(12, 2), default=0.00)
    discount_amount = Column(Numeric(12, 2), default=0.00)
    total_amount    = Column(Numeric(12, 2), nullable=False)

    store           = relationship("Store", back_populates="sales")
    customer        = relationship("Customer", back_populates="sales")
    cashier         = relationship("User", back_populates="sales")
    items           = relationship("SaleItem", back_populates="sale")
    sale_items      = relationship("SaleItem", back_populates="sale")
    invoice         = relationship("Invoice", back_populates="sale", uselist=False)
    credit_entries  = relationship("CreditLedger", back_populates="sale")


class SaleItem(Base):
    __tablename__ = "sale_items"

    sale_item_id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id      = Column(Integer, ForeignKey("sales.sale_id"), nullable=False)
    product_id   = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity     = Column(Integer, nullable=False)
    unit_price   = Column(Numeric(10, 2), nullable=False)
    gst_rate     = Column(Numeric(5, 2), default=0.00)
    discount     = Column(Numeric(10, 2), default=0.00)
    line_total   = Column(Numeric(12, 2), nullable=False)

    sale         = relationship("Sale", back_populates="items")
    product      = relationship("Product", back_populates="sale_items")


class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id     = Column(Integer, primary_key=True, autoincrement=True)
    sale_id        = Column(Integer, ForeignKey("sales.sale_id"), nullable=False, unique=True)
    invoice_number = Column(String(30), nullable=False, unique=True)
    pdf_path       = Column(String(500), nullable=True)
    generated_at   = Column(DateTime, default=datetime.utcnow)

    sale           = relationship("Sale", back_populates="invoice")