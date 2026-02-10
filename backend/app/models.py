
from __future__ import annotations

from sqlalchemy import Column, String
from app.db import Base




class Ack(Base):
    __tablename__ = "ack"

    case_id = Column(String, primary_key=True)
    station_id = Column(String, primary_key=True)
    ack_scope = Column(String, primary_key=True)   # 'case' | 'rule'
    scope_id = Column(String, primary_key=True)    # '*' | rule_id

    acked_at = Column(String, nullable=False)
    acked_by = Column(String, nullable=False)
    comment = Column(String, nullable=True)

    # NEU: nur für rule-acks relevant (case-ack kann None bleiben)
    condition_hash = Column(String, nullable=True)

class AckEvent(Base):
    __tablename__ = "ack_event"

    event_id = Column(String, primary_key=True)   # UUID string
    ts = Column(String, nullable=False)           # ISO-8601 UTC

    case_id = Column(String, nullable=False)
    station_id = Column(String, nullable=False)

    ack_scope = Column(String, nullable=False)
    scope_id = Column(String, nullable=False)

    event_type = Column(String, nullable=False)   # 'ACK' | 'ACK_UPDATE' | 'UNACK' | ...

    user_id = Column(String, nullable=True)       # null for automatic/system events
    payload = Column(String, nullable=True)       # JSON text; use JSONB in Postgres later


class Defer(Base):
    """Aktueller "Schieben"-Status pro Fall/Station.

    Warum extra Tabelle?
    - Wir wollen schnell den letzten Schiebegrund anzeigen (Dashboard)
    - Zusätzlich schreiben wir immer in AckEvent (Audit-Trail)

    Hinweis:
    - In einer echten KISIM-Integration wäre das eher ein Statusfeld im KIS-DB-Modell.
    - Für das MVP ist eine lokale Tabelle ok.
    """

    __tablename__ = "defer"

    case_id = Column(String, primary_key=True)
    station_id = Column(String, primary_key=True)

    deferred_at = Column(String, nullable=False)
    deferred_by = Column(String, nullable=False)
    reason = Column(String, nullable=False)
