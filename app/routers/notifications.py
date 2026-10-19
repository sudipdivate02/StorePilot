"""
Notifications Router — Phase 9
Endpoints:
  GET  /api/v1/notifications              — list notifications
  POST /api/v1/notifications/sweep        — trigger sweep manually
  PATCH /api/v1/notifications/{id}/read   — mark one as read
  POST /api/v1/notifications/read-all     — mark all as read
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.notifications import NotificationsListOut
from app.services import notification_service

router = APIRouter()


@router.get("/notifications", response_model=NotificationsListOut)
def get_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return notification_service.get_notifications(
        db, store_id=current_user["store_id"], unread_only=unread_only,
    )


@router.post("/notifications/sweep")
def trigger_sweep(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger the notification sweep — useful for testing."""
    notification_service.run_sweep(db, store_id=current_user["store_id"])
    return {"message": "Sweep complete. Check GET /notifications for new alerts."}


@router.patch("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return notification_service.mark_read(
        db, store_id=current_user["store_id"], notification_id=notification_id,
    )


@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return notification_service.mark_all_read(db, store_id=current_user["store_id"])