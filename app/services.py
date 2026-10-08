"""Business logic, kept separate from the HTTP layer so it is easy to test and reuse."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas


class SensorNotFound(Exception):
    def __init__(self, sensor_id: int):
        self.sensor_id = sensor_id
        super().__init__(f"Sensor {sensor_id} not found")


def threshold_violation(sensor: models.Sensor, value: float) -> str | None:
    """Return an alert message if the value is outside the sensor's safe range."""
    if sensor.min_threshold is not None and value < sensor.min_threshold:
        return f"{sensor.name}: {value} {sensor.unit} is below minimum {sensor.min_threshold}"
    if sensor.max_threshold is not None and value > sensor.max_threshold:
        return f"{sensor.name}: {value} {sensor.unit} is above maximum {sensor.max_threshold}"
    return None


def ingest_reading(
    db: Session, data: schemas.ReadingCreate
) -> tuple[models.Reading, models.Alert | None]:
    """Store one reading and raise an alert if needed. Does NOT commit:
    the caller decides the transaction boundary (one reading or a whole batch)."""
    sensor = db.get(models.Sensor, data.sensor_id)
    if sensor is None:
        raise SensorNotFound(data.sensor_id)

    reading = models.Reading(sensor_id=sensor.id, value=data.value)
    if data.recorded_at is not None:
        reading.recorded_at = data.recorded_at
    db.add(reading)
    db.flush()  # assigns reading.id so the alert can reference it

    alert = None
    message = threshold_violation(sensor, data.value)
    if message:
        alert = models.Alert(sensor_id=sensor.id, reading_id=reading.id, message=message)
        db.add(alert)
    return reading, alert


def latest_readings_for_node(db: Session, node_id: int) -> list[schemas.LatestReading]:
    """Most recent reading of every sensor on a node, in a single query.

    Uses a window function: number each sensor's readings newest-first,
    then keep only row number 1. Works on PostgreSQL and SQLite.
    """
    ranked = (
        select(
            models.Reading.id.label("reading_id"),
            func.row_number()
            .over(
                partition_by=models.Reading.sensor_id,
                order_by=(models.Reading.recorded_at.desc(), models.Reading.id.desc()),
            )
            .label("rn"),
        )
        .join(models.Sensor, models.Sensor.id == models.Reading.sensor_id)
        .where(models.Sensor.node_id == node_id)
        .subquery()
    )
    rows = db.execute(
        select(models.Sensor, models.Reading)
        .join(models.Reading, models.Reading.sensor_id == models.Sensor.id)
        .join(ranked, ranked.c.reading_id == models.Reading.id)
        .where(ranked.c.rn == 1)
        .order_by(models.Sensor.id)
    ).all()
    return [
        schemas.LatestReading(
            sensor_id=sensor.id,
            sensor_name=sensor.name,
            unit=sensor.unit,
            value=reading.value,
            recorded_at=reading.recorded_at,
        )
        for sensor, reading in rows
    ]
