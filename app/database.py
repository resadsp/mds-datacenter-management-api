"""Podešavanje baze i pomoćne funkcije za sesije."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./datacenter.db")

engine_kwargs = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_sqlite_schema_updates():
    """Dodaje nove kolone u postojeću SQLite šemu ako nedostaju."""
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return

    table_columns = {
        "devices": {
            "deleted_at": "DATETIME",
            "version": "INTEGER NOT NULL DEFAULT 1",
        },
        "racks": {
            "deleted_at": "DATETIME",
            "version": "INTEGER NOT NULL DEFAULT 1",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in table_columns.items():
            existing = {
                row[1]
                for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))

def get_db():
    """Obezbeđuje SQLAlchemy sesiju po zahtevu i bezbedno je zatvara."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()