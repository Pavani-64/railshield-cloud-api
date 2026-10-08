"""Request and response shapes (validated by Pydantic)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Nodes ----
class NodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=200)


class NodeOut(ORMModel):
    id: int
    name: str
    location: str
    created_at: datetime


# ---- Sensors ----
class SensorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    sensor_type: str = Field(min_length=1, max_length=50)
    unit: str = Field(min_length=1, max_length=20)
    min_threshold: float | None = None
    max_threshold: float | None = None

    @model_validator(mode="after")
    def check_range(self):
        if (
            self.min_threshold is not None
            and self.max_threshold is not None
            and self.min_threshold >= self.max_threshold
        ):
            raise ValueError("min_threshold must be lower than max_threshold")
        return self


class SensorOut(ORMModel):
    id: int
    node_id: int
    name: str
    sensor_type: str
    unit: str
    min_threshold: float | None
    max_threshold: float | None


# ---- Readings ----
class ReadingCreate(BaseModel):
    sensor_id: int
    value: float
    recorded_at: datetime | None = None  # defaults to "now" on the server


class ReadingOut(ORMModel):
    id: int
    sensor_id: int
    value: float
    recorded_at: datetime


class LatestReading(BaseModel):
    sensor_id: int
    sensor_name: str
    unit: str
    value: float
    recorded_at: datetime


# ---- Alerts ----
class AlertOut(ORMModel):
    id: int
    sensor_id: int
    reading_id: int
    message: str
    created_at: datetime
    acknowledged: bool


class IngestResult(BaseModel):
    reading: ReadingOut
    alert: AlertOut | None


class BatchIngestResult(BaseModel):
    readings_saved: int
    alerts_raised: int
