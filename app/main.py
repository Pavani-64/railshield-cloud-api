from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, engine
from .routers import alerts, nodes, readings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates any missing tables on startup. (A larger project would use Alembic migrations.)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="RailShield Cloud API",
    description="Backend for RailShield IoT nodes: stores sensor readings and raises alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(nodes.router)
app.include_router(readings.router)
app.include_router(alerts.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
