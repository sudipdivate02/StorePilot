"""
APScheduler jobs — Phase 8 + 9
Runs prediction job and notification sweep daily.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models.user import Store


def _run_daily():
    from app.services import prediction_service, notification_service
    db = SessionLocal()
    try:
        stores = db.query(Store).all()
        for store in stores:
            prediction_service.run_daily_predictions(db, store_id=store.store_id)
            notification_service.run_sweep(db, store_id=store.store_id)
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_daily,
        trigger=CronTrigger(hour=0, minute=5),
        id="daily_job",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler