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

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
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


# -----------------------------------------------------------------------------
# RBAC / Admin / Security Models (MVE-RBAC)
# -----------------------------------------------------------------------------

class User(Base):
    """Interner Benutzer (Identität).

    Hinweis:
      - Authentifizierung (SSO) kommt später. Aktuell wird X-User-Id als Identitäts-
        Hinweis akzeptiert und gegen diese Tabelle gemappt.
      - Autorisierung ist ausschließlich DB-basiert (Rollen/Permissions).
    """

    __tablename__ = "user"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)  # stable external id
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String)  # ISO timestamp (UTC)


class Role(Base):
    """Rolle (stabiler Name, z.B. 'viewer', 'clinician', 'admin')."""

    __tablename__ = "role"

    role_id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "viewer"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)


class Permission(Base):
    """Einzelrecht (String)."""

    __tablename__ = "permission"

    perm_id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "dashboard:view"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)


class RolePermission(Base):
    """Many-to-many: Rollen -> Permissions."""

    __tablename__ = "role_permission"

    role_id: Mapped[str] = mapped_column(String, ForeignKey("role.role_id"), primary_key=True)
    perm_id: Mapped[str] = mapped_column(String, ForeignKey("permission.perm_id"), primary_key=True)


class UserRole(Base):
    """Rollen-Zuweisung (stationsgebunden).

    station_id:
      - konkreter Stationscode (z.B. 'ST01')
      - '*' = gilt für alle Stationen
    """

    __tablename__ = "user_role"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("user.user_id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(String, ForeignKey("role.role_id"), primary_key=True)
    station_id: Mapped[str] = mapped_column(String, primary_key=True, default="*")

    created_at: Mapped[str] = mapped_column(String)  # ISO timestamp (UTC)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class BreakGlassSession(Base):
    """Notfallzugang (zeitlich begrenzte Elevation, append-only + revoke)."""

    __tablename__ = "break_glass_session"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user.user_id"))
    station_id: Mapped[str] = mapped_column(String)  # scope of elevation, '*' allowed

    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)   # ISO timestamp (UTC)
    expires_at: Mapped[str] = mapped_column(String)   # ISO timestamp (UTC)

    revoked_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SecurityEvent(Base):
    """Sicherheits-/Admin-Audit (append-only)."""

    __tablename__ = "security_event"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    ts: Mapped[str] = mapped_column(String)  # ISO timestamp (UTC)

    actor_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    actor_station_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    action: Mapped[str] = mapped_column(String)  # e.g. "ADMIN_USER_CREATE", "RBAC_DENY"
    target_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    success: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON


# -----------------------------------------------------------------------------
# Rules Catalog (editable via Admin UI)
# -----------------------------------------------------------------------------


class RuleDefinition(Base):
    """Regel-Definitionen und Anzeige-Texte.

    Diese Tabelle dient als persistente, versionierbare Quelle für Regeln.
    - Seed: beim Startup werden YAML-Regeln (rules/rules.yaml) als Default
      eingefügt, sofern sie noch nicht existieren.
    - Pflege: Admins können Regeln (Logik + Texte) über /api/admin/rules
      anpassen.

    Wichtiger Sicherheits-Punkt:
      - Die Evaluations-Engine erlaubt nur eine begrenzte Menge Operatoren.
        Dadurch kann man über UI keine "beliebige" Code-Execution erzeugen.
    """

    __tablename__ = "rule_definition"

    rule_id: Mapped[str] = mapped_column(String, primary_key=True)

    # UI / Anzeige
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text)  # Kurztext
    explanation: Mapped[str] = mapped_column(Text)  # Langtext

    # Logik
    category: Mapped[str] = mapped_column(String, default="medical")
    severity: Mapped[str] = mapped_column(String)  # "OK"|"WARN"|"CRITICAL"
    metric: Mapped[str] = mapped_column(String)
    operator: Mapped[str] = mapped_column(String)
    value_json: Mapped[str] = mapped_column(Text)  # JSON-encoded expected value

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)



__all__ = [
    "Ack",
    "AckEvent",
    "DayState",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "BreakGlassSession",
    "SecurityEvent",
    "RuleDefinition",
]
