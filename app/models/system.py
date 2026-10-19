"""
Group E — System
Tables: notifications, prediction_history, audit_logs
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, Numeric, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    store_id        = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    type            = Column(String(50), nullable=False)  # LOW_STOCK/EXPIRY/UDHAR/PREDICTION
    message         = Column(String(500), nullable=False)
    is_read         = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)


class PredictionHistory(Base):
    __tablename__ = "prediction_history"

    prediction_id   = Column(Integer, primary_key=True, autoincrement=True)
    product_id      = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    prediction_date = Column(DateTime, default=datetime.utcnow)
    method_used     = Column(String(50), nullable=False)  # SMA / WMA / Holt-Winters
    forecast_qty    = Column(Integer, nullable=False)
    confidence_low  = Column(Integer, nullable=True)
    confidence_high = Column(Integer, nullable=True)
    actual_qty      = Column(Integer, nullable=True)
    mape_error      = Column(Numeric(8, 4), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    product         = relationship("Product", back_populates="predictions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id      = Column(Integer, primary_key=True, autoincrement=True)
    store_id    = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    action      = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id   = Column(Integer, nullable=True)
    ip_address  = Column(String(45), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)