"""
Group C — Sales & Finance (customer side)
Tables: customers, credit_ledger
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric,
    DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id    = Column(Integer, primary_key=True, autoincrement=True)
    store_id       = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    name           = Column(String(150), nullable=False)
    phone          = Column(String(15), nullable=True)
    address        = Column(String(400), nullable=True)
    credit_balance = Column(Numeric(12, 2), default=0.00)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store          = relationship("Store", back_populates="customers")
    sales          = relationship("Sale", back_populates="customer")
    credit_entries = relationship("CreditLedger", back_populates="customer")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    ledger_id        = Column(Integer, primary_key=True, autoincrement=True)
    customer_id      = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    sale_id          = Column(Integer, ForeignKey("sales.sale_id"), nullable=True)
    transaction_type = Column(
        Enum("credit_given", "payment_received", name="credit_type_enum"),
        nullable=False
    )
    amount           = Column(Numeric(12, 2), nullable=False)
    balance_after    = Column(Numeric(12, 2), nullable=False)
    note             = Column(String(300), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)

    customer         = relationship("Customer", back_populates="credit_entries")
    sale             = relationship("Sale", back_populates="credit_entries")