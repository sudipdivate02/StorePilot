"""
Reports Router — Phase 10
All 6 report endpoints returning JSON.
Frontend renders and offers CSV download.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.schemas.reports import (
    SalesSummaryReport, ProfitLossReport, GSTReport,
    TopProductsReport, UdharReport, PurchaseReport,
)
from app.services import report_service

router = APIRouter()


@router.get("/reports/sales", response_model=SalesSummaryReport)
def sales_summary(
    months_back: int = Query(0, ge=0, le=11),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return report_service.sales_summary(db, store_id=current_user["store_id"], months_back=months_back)


@router.get("/reports/profit-loss", response_model=ProfitLossReport)
def profit_loss(
    months_back: int = Query(0, ge=0, le=11),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return report_service.profit_loss(db, store_id=current_user["store_id"], months_back=months_back)


@router.get("/reports/gst", response_model=GSTReport)
def gst_report(
    months_back: int = Query(0, ge=0, le=11),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return report_service.gst_report(db, store_id=current_user["store_id"], months_back=months_back)


@router.get("/reports/top-products", response_model=TopProductsReport)
def top_products(
    months_back: int = Query(0, ge=0, le=11),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return report_service.top_products(db, store_id=current_user["store_id"], months_back=months_back)


@router.get("/reports/udhar", response_model=UdharReport)
def udhar_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return report_service.udhar_report(db, store_id=current_user["store_id"])


@router.get("/reports/purchases", response_model=PurchaseReport)
def purchase_report(
    months_back: int = Query(0, ge=0, le=11),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return report_service.purchase_report(db, store_id=current_user["store_id"], months_back=months_back)