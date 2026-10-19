"""
Group A — Identity & Access
Tables: stores, roles, users
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, ForeignKey, JSON, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    store_id    = Column(Integer, primary_key=True, autoincrement=True)
    store_name  = Column(String(200), nullable=False)
    owner_name  = Column(String(100), nullable=False)
    phone       = Column(String(15), nullable=False, unique=True)
    email       = Column(String(100), nullable=True)
    address     = Column(String(500), nullable=True)
    gst_number  = Column(String(20), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    users       = relationship("User", back_populates="store")
    products    = relationship("Product", back_populates="store")
    categories  = relationship("Category", back_populates="store")
    customers   = relationship("Customer", back_populates="store")
    suppliers   = relationship("Supplier", back_populates="store")
    sales       = relationship("Sale", back_populates="store")


class Role(Base):
    __tablename__ = "roles"

    role_id          = Column(Integer, primary_key=True, autoincrement=True)
    role_name        = Column(String(50), nullable=False, unique=True)  # Owner/Manager/Cashier
    permissions_json = Column(JSON, nullable=True)

    users            = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    user_id       = Column(Integer, primary_key=True, autoincrement=True)
    store_id      = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    role_id       = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    name          = Column(String(100), nullable=False)
    phone         = Column(String(15), nullable=False, unique=True)
    email         = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store         = relationship("Store", back_populates="users")
    role          = relationship("Role", back_populates="users")
    sales         = relationship("Sale", back_populates="cashier")