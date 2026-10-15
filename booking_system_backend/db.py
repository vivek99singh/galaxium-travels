import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from models import Base

# Get database URL from environment, fallback to SQLite for local dev
SQLALCHEMY_DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'sqlite:///./booking.db'
)

# PostgreSQL doesn't need check_same_thread
connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith('sqlite'):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns():
    """create_all() doesn't add columns to existing tables; add the ones added since."""
    insp = inspect(engine)
    if 'waitlist_entries' not in insp.get_table_names():
        return
    columns = {c['name'] for c in insp.get_columns('waitlist_entries')}
    if 'offer_expires_at' not in columns:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE waitlist_entries ADD COLUMN offer_expires_at VARCHAR'))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()