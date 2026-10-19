"""
Group B — Product & Inventory
Tables: categories, products, inventory, inventory_history
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, Date, Numeric, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    category_id   = Column(Integer, primary_key=True, autoincrement=True)
    store_id      = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    category_name = Column(String(100), nullable=False)
    description   = Column(String(300), nullable=True)

    store         = relationship("Store", back_populates="categories")
    products      = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    product_id    = Column(Integer, primary_key=True, autoincrement=True)
    store_id      = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    category_id   = Column(Integer, ForeignKey("categories.category_id"), nullable=True)
    name          = Column(String(200), nullable=False)
    barcode       = Column(String(50), nullable=True)
    unit          = Column(String(20), default="pcs")
    cost_price    = Column(Numeric(10, 2), nullable=False)
    selling_price = Column(Numeric(10, 2), nullable=False)
    gst_rate      = Column(Numeric(5, 2), default=0.00)
    reorder_level = Column(Integer, default=5)
    expiry_tracked= Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store         = relationship("Store", back_populates="products")
    category      = relationship("Category", back_populates="products")
    inventory     = relationship("Inventory", back_populates="product", uselist=False)
    history       = relationship("InventoryHistory", back_populates="product")
    sale_items    = relationship("SaleItem", back_populates="product")
    predictions   = relationship("PredictionHistory", back_populates="product")


class Inventory(Base):
    __tablename__ = "inventory"

    inventory_id    = Column(Integer, primary_key=True, autoincrement=True)
    product_id      = Column(Integer, ForeignKey("products.product_id"), nullable=False, unique=True)
    current_stock   = Column(Integer, default=0)
    batch_number    = Column(String(50), nullable=True)
    expiry_date     = Column(Date, nullable=True)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product         = relationship("Product", back_populates="inventory")


class InventoryHistory(Base):
    __tablename__ = "inventory_history"

    history_id     = Column(Integer, primary_key=True, autoincrement=True)
    product_id     = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    change_type    = Column(
        Enum("stock_in", "stock_out", "adjustment", name="change_type_enum"),
        nullable=False
    )
    quantity       = Column(Integer, nullable=False)
    reference_type = Column(String(50), nullable=True)   # sale / purchase_order / manual
    reference_id   = Column(Integer, nullable=True)
    note           = Column(String(300), nullable=True)
    created_by     = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    product        = relationship("Product", back_populates="history")