from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[schemas.AlertOut])
def list_alerts(
    acknowledged: bool | None = None,
    node_id: int | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Alerts, newest first. Filter by status (e.g. ?acknowledged=false) or by node."""
    query = select(models.Alert)
    if acknowledged is not None:
        query = query.where(models.Alert.acknowledged == acknowledged)
    if node_id is not None:
        query = query.join(models.Sensor).where(models.Sensor.node_id == node_id)
    query = query.order_by(models.Alert.created_at.desc(), models.Alert.id.desc()).limit(limit)
    return db.scalars(query).all()


@router.patch("/{alert_id}/acknowledge", response_model=schemas.AlertOut)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Mark an alert as seen by an operator."""
    alert = db.get(models.Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Alert {alert_id} not found")
    alert.acknowledged = True
    db.commit()
    return alert
