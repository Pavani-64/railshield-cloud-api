from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db

router = APIRouter(prefix="/nodes", tags=["nodes"])


def get_node_or_404(db: Session, node_id: int) -> models.Node:
    node = db.get(models.Node, node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Node {node_id} not found")
    return node


@router.post("", response_model=schemas.NodeOut, status_code=status.HTTP_201_CREATED)
def create_node(data: schemas.NodeCreate, db: Session = Depends(get_db)):
    node = models.Node(**data.model_dump())
    db.add(node)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Node '{data.name}' already exists")
    return node


@router.get("", response_model=list[schemas.NodeOut])
def list_nodes(db: Session = Depends(get_db)):
    return db.scalars(select(models.Node).order_by(models.Node.id)).all()


@router.get("/{node_id}", response_model=schemas.NodeOut)
def get_node(node_id: int, db: Session = Depends(get_db)):
    return get_node_or_404(db, node_id)


@router.post(
    "/{node_id}/sensors", response_model=schemas.SensorOut, status_code=status.HTTP_201_CREATED
)
def add_sensor(node_id: int, data: schemas.SensorCreate, db: Session = Depends(get_db)):
    get_node_or_404(db, node_id)
    sensor = models.Sensor(node_id=node_id, **data.model_dump())
    db.add(sensor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Node {node_id} already has a sensor named '{data.name}'"
        )
    return sensor


@router.get("/{node_id}/sensors", response_model=list[schemas.SensorOut])
def list_sensors(node_id: int, db: Session = Depends(get_db)):
    return get_node_or_404(db, node_id).sensors


@router.get("/{node_id}/latest", response_model=list[schemas.LatestReading])
def latest_readings(node_id: int, db: Session = Depends(get_db)):
    """Latest value of every sensor on this node (what a live dashboard would show)."""
    get_node_or_404(db, node_id)
    return services.latest_readings_for_node(db, node_id)
