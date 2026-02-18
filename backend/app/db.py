"""Datenbank-Anbindung.

Unterstützt SQLite (Standard/Entwicklung) und PostgreSQL (Produktion).

Konfiguration über Umgebungsvariable DATABASE_URL:
  - Nicht gesetzt / leer: SQLite (data/app.db)
  - postgresql://...: PostgreSQL

Wichtig (MVP-Realität):
  - Wir verwenden *keine* vollwertigen Migrationen (z.B. Alembic).
  - Stattdessen prüft `init_db()` beim Start, ob neue Spalten/Tabellen fehlen,
    und ergänzt diese minimal per `ALTER TABLE ... ADD COLUMN ...`.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# --- Database URL Resolution ---
_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if _DATABASE_URL:
    DB_URL = _DATABASE_URL
    _IS_SQLITE = False
else:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"
    DATA_DIR.mkdir(exist_ok=True)
    DB_URL = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
    _IS_SQLITE = True

# --- Engine Configuration ---
_engine_kwargs = {"pool_pre_ping": True}

if _IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    _engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_engine(DB_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    if _IS_SQLITE:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.execute(text("PRAGMA busy_timeout=5000;"))
            conn.commit()

    Base.metadata.create_all(bind=engine)
    _ensure_schema()


def _ensure_schema() -> None:
    """Ergänzt fehlende Spalten für bestehende DB-Dateien."""
    insp = inspect(engine)

    def cols(table: str) -> set[str]:
        if table not in insp.get_table_names():
            return set()
        return {c["name"] for c in insp.get_columns(table)}

    def safe_add(conn, table: str, column: str, col_type: str = "TEXT"):
        if table not in insp.get_table_names():
            return
        if column not in cols(table):
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))

    with engine.begin() as conn:
        safe_add(conn, "ack", "condition_hash")
        safe_add(conn, "ack", "business_date")
        safe_add(conn, "ack", "version", "INTEGER")
        safe_add(conn, "ack", "action")
        safe_add(conn, "ack", "shift_code")
        safe_add(conn, "security_event", "user_agent")
        safe_add(conn, "security_event", "details")
        safe_add(conn, "case_data", "imported_at")
        safe_add(conn, "case_data", "imported_by")
        safe_add(conn, "case_data", "source")
        # Neue klinische Felder (v2)
        safe_add(conn, "case_data", "is_voluntary", "BOOLEAN")
        safe_add(conn, "case_data", "treatment_plan_date")
        safe_add(conn, "case_data", "sdep_complete", "BOOLEAN")
        safe_add(conn, "case_data", "ekg_last_date")
        safe_add(conn, "case_data", "ekg_last_reported", "BOOLEAN")
        safe_add(conn, "case_data", "ekg_entry_date")
        safe_add(conn, "case_data", "clozapin_active", "BOOLEAN")
        safe_add(conn, "case_data", "clozapin_start_date")
        safe_add(conn, "case_data", "neutrophils_last_date")
        safe_add(conn, "case_data", "neutrophils_last_value")
        safe_add(conn, "case_data", "troponin_last_date")
        safe_add(conn, "case_data", "cbc_last_date")
        safe_add(conn, "case_data", "emergency_bem_start_date")
        safe_add(conn, "case_data", "emergency_med_start_date")
        safe_add(conn, "case_data", "allergies_recorded", "BOOLEAN")
