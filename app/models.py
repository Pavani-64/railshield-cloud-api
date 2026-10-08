"""Database tables.

nodes 1──* sensors 1──* readings
                 1──* alerts *──1 readings
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Node(Base):
    """A field device installed along the track (one ESP32 board in RailShield)."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    location: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="node", cascade="all, delete-orphan"
    )


class Sensor(Base):
    """One sensor on a node, with optional safe-range thresholds."""

    __tablename__ = "sensors"
    __table_args__ = (UniqueConstraint("node_id", "name", name="uq_sensor_name_per_node"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    sensor_type: Mapped[str] = mapped_column(String(50))
    unit: Mapped[str] = mapped_column(String(20))
    min_threshold: Mapped[float | None] = mapped_column(Float)
    max_threshold: Mapped[float | None] = mapped_column(Float)

    node: Mapped[Node] = relationship(back_populates="sensors")


class Reading(Base):
    """A single measurement. This table grows fastest, so it is indexed for
    "readings of sensor X between time A and B" queries."""

    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_sensor_time", "sensor_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    value: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    """Raised automatically when a reading falls outside its sensor's thresholds."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id", ondelete="CASCADE"), index=True
    )
    reading_id: Mapped[int] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), unique=True
    )
    message: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
