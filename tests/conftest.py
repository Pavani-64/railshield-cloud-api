"""Test setup: each test gets a fresh, empty database.

By default tests use an in-memory SQLite database. To run them against PostgreSQL,
set TEST_DATABASE_URL, e.g.
    TEST_DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/railshield_test
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite://")

if TEST_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
else:
    engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sensor(client):
    """A node with one temperature sensor whose safe range is 0-60."""
    node = client.post("/nodes", json={"name": "node-1", "location": "KM 12"}).json()
    return client.post(
        f"/nodes/{node['id']}/sensors",
        json={
            "name": "temp",
            "sensor_type": "temperature",
            "unit": "C",
            "min_threshold": 0,
            "max_threshold": 60,
        },
    ).json()
