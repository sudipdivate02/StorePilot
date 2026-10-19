"""
Predictions Router — Phase 8
Endpoints:
  GET  /api/v1/predictions              — all predictions for the store
  GET  /api/v1/predictions/{id}         — single product prediction
  POST /api/v1/predictions/{id}/override — confirm or override a prediction
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_role
from app.schemas.predictions import PredictionOut, PredictionOverride, PredictionsListOut
from app.services import prediction_service

router = APIRouter()


@router.get("/predictions", response_model=PredictionsListOut)
def get_all_predictions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return prediction_service.get_all_predictions(
        db, store_id=current_user["store_id"],
    )


@router.get("/predictions/{product_id}", response_model=PredictionOut)
def get_prediction(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return prediction_service.get_prediction(
        db, store_id=current_user["store_id"], product_id=product_id,
    )


@router.post("/predictions/{product_id}/override")
def override_prediction(
    product_id: int,
    data: PredictionOverride,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["Owner", "Manager"])),
):
    return prediction_service.override_prediction(
        db, store_id=current_user["store_id"],
        product_id=product_id, data=data,
    )