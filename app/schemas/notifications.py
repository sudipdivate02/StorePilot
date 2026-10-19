from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class NotificationOut(BaseModel):
    notification_id: int
    type: str          # low_stock | expiry | credit_due | open_po
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationsListOut(BaseModel):
    unread_count: int
    notifications: List[NotificationOut]