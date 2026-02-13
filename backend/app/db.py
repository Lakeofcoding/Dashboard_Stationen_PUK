"""Datenbank-Anbindung.

Für den Prototyp wird SQLite genutzt.

Wichtig (MVP-Realität):
  - Wir verwenden *keine* vollwertigen Migrationen (z.B. Alembic).
  - Stattdessen prüft `init_db()` beim Start, ob neue Spalten/Tabellen fehlen,
    und ergänzt diese minimal per `ALTER TABLE ... ADD COLUMN ...`.

Das ist nicht "best practice" für Produktion, reicht aber für den Prototyp.
"""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_URL = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def init_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.execute(text("PRAGMA busy_timeout=5000;"))
        conn.commit()

    # 1) Tabellen anlegen (falls noch nicht vorhanden)
    Base.metadata.create_all(bind=engine)

    # 2) Mini-Migration: fehlende Spalten ergänzen.
    #    Das ist bewusst sehr simpel gehalten.
    _ensure_schema()


def _ensure_schema() -> None:
    """Ergänzt fehlende Spalten für bestehende DB-Dateien.

    Hintergrund:
      - `create_all()` fügt keine neuen Spalten zu bestehenden Tabellen hinzu.
      - Für den Prototyp wollen wir trotzdem ohne manuelles Löschen der DB
        weiterentwickeln können.
    """

    insp = inspect(engine)

    def cols(table: str) -> set[str]:
        if table not in insp.get_table_names():
            return set()
        return {c["name"] for c in insp.get_columns(table)}

    with engine.begin() as conn:
        # --- Tabelle ack: neue Spalten seit Version 0.3.x
        ack_cols = cols("ack")
        if "condition_hash" not in ack_cols:
            conn.execute(text("ALTER TABLE ack ADD COLUMN condition_hash TEXT"))
        if "business_date" not in ack_cols:
            conn.execute(text("ALTER TABLE ack ADD COLUMN business_date TEXT"))
        if "version" not in ack_cols:
            conn.execute(text("ALTER TABLE ack ADD COLUMN version INTEGER"))
        if "action" not in ack_cols:
            conn.execute(text("ALTER TABLE ack ADD COLUMN action TEXT"))
        if "shift_code" not in ack_cols:
            conn.execute(text("ALTER TABLE ack ADD COLUMN shift_code TEXT"))

        # day_state wird von SQLAlchemy automatisch angelegt, wenn sie fehlt.

        # --- Tabelle security_event: neue Spalten für User-Agent / Details
        sec_cols = cols("security_event")
        if "user_agent" not in sec_cols:
            conn.execute(text("ALTER TABLE security_event ADD COLUMN user_agent TEXT"))
        if "details" not in sec_cols:
            conn.execute(text("ALTER TABLE security_event ADD COLUMN details TEXT"))
