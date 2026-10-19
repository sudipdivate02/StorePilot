"""
Dashboard Router — Phase 7
Single endpoint: GET /api/v1/dashboard/summary
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard_service

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return dashboard_service.get_summary(db, store_id=current_user["store_id"])