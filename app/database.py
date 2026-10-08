"""Database connection and session handling.

The connection string comes from the DATABASE_URL environment variable (or a .env file).
PostgreSQL is the intended database; SQLite is only a fallback for a quick local start.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./railshield.db")

# SQLite needs this flag because FastAPI may use the connection from different threads.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: opens one session per request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
