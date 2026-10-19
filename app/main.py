"""
StorePilot — FastAPI entry point
Run with: uvicorn app.main:app --reload
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database import Base, engine
from app.models import (
    user, product, sale,
    customer, supplier, system
)
from app.routers import auth, inventory, billing, customers, suppliers, dashboard, predictions, notifications, reports
from app.scheduler.jobs import start_scheduler

load_dotenv()

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="StorePilot API",
    description="AI-powered Business Operating System for Kirana Stores",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5500").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(inventory.router, prefix="/api/v1", tags=["Inventory"])
app.include_router(billing.router, prefix="/api/v1", tags=["Billing"])
app.include_router(customers.router, prefix="/api/v1", tags=["Customers"])
app.include_router(suppliers.router, prefix="/api/v1", tags=["Suppliers"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(predictions.router, prefix="/api/v1", tags=["Predictions"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])


@app.on_event("startup")
def startup_event():
    start_scheduler()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "StorePilot", "version": "0.1.0"}