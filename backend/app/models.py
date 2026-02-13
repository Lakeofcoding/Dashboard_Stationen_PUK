# backend/app/models.py
from __future__ import annotations

"""
SQLAlchemy-Modelle (Datenbanktabellen) für das Dashboard.

Begriffe / Zweck:
- Ack      : "aktueller Zustand" einer Quittierung / eines Schiebens.
             Das ist kein Log, sondern der jeweils letzte Status pro Key.
- AckEvent : Audit-Log (append-only). Jede Aktion wird zusätzlich als Event
             protokolliert, damit man später nachvollziehen kann, was passiert ist.
- DayState : Pro Station und Geschäftstag wird eine Tagesversion ("Vers") geführt.
             Reset erhöht die Version -> alte Acks/Shift des Tages sind automatisch
             ungültig, ohne dass man Daten löschen muss.

Hinweis:
- Wir nutzen SQLite. Zusammengesetzte Primärschlüssel sind erlaubt.
- Typen sind bewusst simpel gehalten (TEXT/INTEGER), weil es ein MVP ist.
"""

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Ack(Base):
    """
    Aktueller Quittierungs-/Schiebe-Zustand.

    Primärschlüssel (zusammengesetzt):
      (case_id, station_id, ack_scope, scope_id)

    Beispiele:
      - ack_scope="rule", scope_id="<RULE_ID>"  -> Einzelmeldung quittiert/geschoben
      - ack_scope="case", scope_id="*"          -> Fall quittiert (heutige Vers)
    """

    __tablename__ = "ack"

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    station_id: Mapped[str] = mapped_column(String, primary_key=True)
    ack_scope: Mapped[str] = mapped_column(String, primary_key=True)  # "rule" | "case"
    scope_id: Mapped[str] = mapped_column(String, primary_key=True)   # RULE_ID oder "*"

    # wann/wem/Kommentar
    acked_at: Mapped[str] = mapped_column(String)   # ISO timestamp (UTC)
    acked_by: Mapped[str] = mapped_column(String)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Damit Acks nur gelten, wenn die zugrundeliegende Bedingung gleich geblieben ist
    condition_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Geschäftstag + Tagesversion ("Vers") für Reset-Funktion
    business_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # YYYY-MM-DD (Europe/Zurich)
    version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Aktionstyp:
    # - "ACK"   = Quittiert
    # - "SHIFT" = Geschoben (a/b/c)
    action: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    shift_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "a"|"b"|"c"


class AckEvent(Base):
    """
    Audit-Log (append-only).

    Jede Benutzeraktion wird als Event geschrieben:
      - ACK_CREATE / ACK_UPDATE
      - SHIFT_CREATE / SHIFT_UPDATE
      - RESET_DAY
      etc.
    """

    __tablename__ = "ack_event"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    ts: Mapped[str] = mapped_column(String)  # ISO timestamp (UTC)

    case_id: Mapped[str] = mapped_column(String)
    station_id: Mapped[str] = mapped_column(String)

    ack_scope: Mapped[str] = mapped_column(String)
    scope_id: Mapped[str] = mapped_column(String)

    event_type: Mapped[str] = mapped_column(String)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # JSON als String (damit SQLite keine Sonderbehandlung braucht)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DayState(Base):
    """
    Pro Station und Geschäftstag: aktuelle Tagesversion ("Vers").

    Zusammengesetzter Primärschlüssel:
      (station_id, business_date)

    Beispiel:
      station_id="A1", business_date="2026-02-13", version=1
      -> nach Reset: version=2
    """

    __tablename__ = "day_state"

    station_id: Mapped[str] = mapped_column(String, primary_key=True)
    business_date: Mapped[str] = mapped_column(String, primary_key=True)  # YYYY-MM-DD

    version: Mapped[int] = mapped_column(Integer, default=1)


__all__ = ["Ack", "AckEvent", "DayState"]
