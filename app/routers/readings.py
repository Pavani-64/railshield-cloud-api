from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db

router = APIRouter(tags=["readings"])


@router.post(
    "/readings", response_model=schemas.IngestResult, status_code=status.HTTP_201_CREATED
)
def ingest_reading(data: schemas.ReadingCreate, db: Session = Depends(get_db)):
    """Receive one reading from a node. Raises an alert if it is out of range."""
    try:
        reading, alert = services.ingest_reading(db, data)
    except services.SensorNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    db.commit()
    return {"reading": reading, "alert": alert}


@router.post(
    "/readings/batch",
    response_model=schemas.BatchIngestResult,
    status_code=status.HTTP_201_CREATED,
)
def ingest_batch(
    data: list[schemas.ReadingCreate] = ...,
    db: Session = Depends(get_db),
):
    """Receive many readings at once (e.g. a node uploading after being offline).

    All-or-nothing: if any reading refers to an unknown sensor, nothing is saved.
    """
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Batch is empty")
    if len(data) > 1000:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Maximum 1000 readings per batch")

    alerts = 0
    try:
        for item in data:
            _, alert = services.ingest_reading(db, item)
            alerts += alert is not None
    except services.SensorNotFound as e:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{e}; no readings were saved")
    db.commit()
    return {"readings_saved": len(data), "alerts_raised": alerts}


@router.get("/sensors/{sensor_id}/readings", response_model=list[schemas.ReadingOut])
def sensor_history(
    sensor_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Readings for one sensor, newest first, optionally within a time range."""
    if db.get(models.Sensor, sensor_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sensor {sensor_id} not found")

    query = select(models.Reading).where(models.Reading.sensor_id == sensor_id)
    if start is not None:
        query = query.where(models.Reading.recorded_at >= start)
    if end is not None:
        query = query.where(models.Reading.recorded_at <= end)
    query = query.order_by(models.Reading.recorded_at.desc(), models.Reading.id.desc()).limit(limit)
    return db.scalars(query).all()
