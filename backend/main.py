"""
Datei: backend/main.py

Zweck:
- Backend-/Serverlogik dieser Anwendung.
- Kommentare wurden ergänzt, um Einstieg und Wartung zu erleichtern.

Hinweis:
- Sicherheitsrelevante Checks (RBAC/Permissions) werden serverseitig erzwungen.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
import yaml
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from app.ack_store import AckStore
from app.auth import AuthContext, get_auth_context, require_ctx
from app.audit import log_security_event
from app.rbac import (
    activate_break_glass,
    require_permission,
    revoke_break_glass,
    seed_rbac,
)

from app.db import SessionLocal, init_db
from app.models import DayState, RuleDefinition

# -----------------------------------------------------------------------------
# Helpers: condition hash
# -----------------------------------------------------------------------------

# Funktion: compute_condition_hash – kapselt eine wiederverwendbare Backend-Operation.
def compute_condition_hash(
    *,
    rule_id: str,
    metric: str,
    operator: str,
    expected,
    actual,
    discharge_date: date | None,
) -> str:
    payload = {
        "rule_id": rule_id,
        "metric": metric,
        "operator": operator,
        "expected": expected,
        "actual": actual,
        "discharge_date": discharge_date.isoformat() if discharge_date else None,
        "ruleset_version": "v1",
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------

app = FastAPI(title="Dashboard Backend (MVP)", version="0.3.0", debug=True)
ack_store = AckStore()


@app.on_event("startup")
# Funktion: _startup – kapselt eine wiederverwendbare Backend-Operation.
def _startup():
    init_db()
    with SessionLocal() as db:
        # 1. Rollen und Permissions anlegen
        seed_rbac(db)

        # 1b. Regeln (rules.yaml) als Default in die DB seeden (nur wenn neu)
        seed_rule_definitions(db)
        
        from app.models import User, UserRole
        from datetime import datetime
        
        # 2. Sicherstellen, dass der User 'demo' existiert
        user = db.query(User).filter(User.user_id == "demo").first()
        if not user:
            user = User(user_id="demo", full_name="Demo User", is_active=True)
            db.add(user)
            db.flush() 
        
        # 3. Rolle 'admin' dem User 'demo' zuweisen
        existing_role = db.query(UserRole).filter(
            UserRole.user_id == "demo", 
            UserRole.role_id == "admin"
        ).first()
        
        if not existing_role:
            # Hier fügen wir die fehlenden Felder hinzu, um den IntegrityError zu beheben
            new_user_role = UserRole(
                user_id="demo", 
                role_id="admin",
                station_id="*",      # "*" bedeutet oft "alle Stationen" in deinem System
                created_at=datetime.now().isoformat(), # Zeitstempel als String
                created_by="system"  # Verpflichtendes Feld aus deinem Modell
            )
            db.add(new_user_role)
            print("Rolle 'admin' wurde User 'demo' neu zugewiesen.")
        
        db.commit()
    print("Sicherheits-System erfolgreich initialisiert.")

# -----------------------------------------------------------------------------
# API models
# -----------------------------------------------------------------------------

Severity = Literal["OK", "WARN", "CRITICAL"]


# Funktion: today_local – kapselt eine wiederverwendbare Backend-Operation.
def today_local() -> date:
    """Business date for acknowledgement expiry (Europe/Zurich)."""
    return datetime.now(ZoneInfo("Europe/Zurich")).date()


# Funktion: get_day_version – kapselt eine wiederverwendbare Backend-Operation.
def get_day_version(*, station_id: str) -> int:
    """Liefert die aktuelle Tagesversion ("Vers") für eine Station.

    - Für jede Station und jeden Geschäftstag existiert genau ein `day_state`.
    - Beim ersten Zugriff an einem Tag wird der Datensatz angelegt (Version 1).
    - Bei "Reset" wird diese Version erhöht.

    Die Version wird verwendet, um Acks am selben Tag invalidieren zu können,
    ohne alte Datensätze löschen zu müssen.
    """

    bdate = today_local().isoformat()
    with SessionLocal() as db:
        row = db.get(DayState, (station_id, bdate))
        if row is None:
            row = DayState(station_id=station_id, business_date=bdate, version=1)
            db.add(row)
            db.commit()
            db.refresh(row)
        return int(row.version)


# Funktion: _parse_iso_dt – kapselt eine wiederverwendbare Backend-Operation.
def _parse_iso_dt(s: str) -> datetime:
    # Handle trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


# Funktion: _ack_is_valid_today – kapselt eine wiederverwendbare Backend-Operation.
def _ack_is_valid_today(*, acked_at_iso: str, business_date: str | None, version: int | None, current_version: int) -> bool:
    """Prüft, ob eine Quittierung/Shift *heute* gültig ist.

    Gültigkeitsregeln:
      - Primär (neue Semantik): Wenn `business_date` UND `version` vorhanden sind,
        muss beides für *heute* stimmen:
          * business_date == heutiger Geschäftstag (Europe/Zurich)
          * version == aktuelle Tagesversion (Vers)
      - Legacy-Fallback: Falls `business_date` oder `version` fehlen (Altdaten),
        verwenden wir `acked_at` als Datum-Check.

    Hintergrund:
      - Reset inkrementiert die Tagesversion. Damit müssen alte Acks für den
        gleichen Geschäftstag ungültig werden. Ein globaler Fallback auf
        `acked_at` würde diese Invalidation aushebeln.
    """

    today = today_local().isoformat()

    # Strikte Logik bei vollständigen Datensätzen
    if business_date is not None and version is not None:
        return business_date == today and version == current_version

    # Fallback nur für Legacy-Daten ohne business_date/version
    try:
        dt = datetime.fromisoformat(acked_at_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False

    return dt.astimezone(ZoneInfo("Europe/Zurich")).date().isoformat() == today


# Klasse: Alert – strukturiert Daten/Logik (z.B. Modelle, Services).
class Alert(BaseModel):
    rule_id: str
    severity: Severity
    # Für die Filter-Sicht: "completeness" (Vollständigkeit) oder "medical" (Werte)
    category: Literal["completeness", "medical"] = "medical"
    message: str
    explanation: str
    condition_hash: str


# Klasse: CaseSummary – strukturiert Daten/Logik (z.B. Modelle, Services).
class CaseSummary(BaseModel):
    case_id: str
    patient_id: str

    clinic: str
    center: str
    station_id: str

    admission_date: date
    discharge_date: Optional[date] = None

    severity: Severity
    top_alert: Optional[str] = None

    # For station overview: counts of *active* (non-acked-today) alerts
    critical_count: int = 0
    warn_count: int = 0

    # case-level ack ("Fall vollständig") – only possible after discharge
    acked_at: Optional[str] = None


# Klasse: CaseDetail – strukturiert Daten/Logik (z.B. Modelle, Services).
class CaseDetail(CaseSummary):
    # For UI convenience
    honos: Optional[int] = None
    bscl: Optional[int] = None
    bfs_complete: bool = False

    alerts: list[Alert] = Field(default_factory=list)

    # rule_id -> Status der Einzelmeldung für *heute*.
    # Beispiel:
    #   {"HONOS_ENTRY_MISSING_WARN": {"state": "ACK", "ts": "..."}}
    #   {"BFS_INCOMPLETE": {"state": "SHIFT", "shift_code": "b", "ts": "..."}}
    rule_states: dict[str, dict[str, Any]] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Dummy data (your schema)
# -----------------------------------------------------------------------------

STATION_CENTER = {
    "A1": "ZAPE",
    "B0": "ZDAP",
    "B2": "ZDAP",
}
CLINIC_DEFAULT = "EPP"



DUMMY_CASES = [
  # 1) Eintritt: HONOS/BSCL fehlen, >3 Tage seit Eintritt => CRITICAL
  {
    "case_id": "4645342",
    "patient_id": "4534234",
    "clinic": "EPP",
    "station_id": "A1",
    "center": "ZAPE",
    "admission_date": date(2026, 1, 1),
    "discharge_date": None,

    "honos_entry_total": None,
    "honos_entry_date": None,
    "honos_discharge_total": None,
    "honos_discharge_date": None,
    "honos_discharge_suicidality": None,

    "bscl_total_entry": None,
    "bscl_entry_date": None,
    "bscl_total_discharge": None,
    "bscl_discharge_date": None,
    "bscl_discharge_suicidality": None,

    "bfs_1": 11, "bfs_2": None, "bfs_3": None,

    "isolations": []
  },

  # 2) Eintritt HONOS/BSCL vorhanden, aber starke Verschlechterung >5 => WARN (Risk)
  {
    "case_id": "4645343",
    "patient_id": "4534235",
    "clinic": "EPP",
    "station_id": "B0",
    "center": "ZDAP",
    "admission_date": date(2026, 1, 10),
    "discharge_date": date(2026, 1, 20),

    "honos_entry_total": 12,
    "honos_entry_date": date(2026, 1, 11),
    "honos_discharge_total": 20,
    "honos_discharge_date": date(2026, 1, 20),
    "honos_discharge_suicidality": 1,

    "bscl_total_entry": 40,
    "bscl_entry_date": date(2026, 1, 11),
    "bscl_total_discharge": 50,
    "bscl_discharge_date": date(2026, 1, 20),
    "bscl_discharge_suicidality": 2,

    "bfs_1": 10, "bfs_2": 12, "bfs_3": 9,

    "isolations": []
  },

  # 3) Austritt: HONOS/BSCL fehlen, discharge vor 5 Tagen => CRITICAL (Austrittfenster 3 Tage)
  {
    "case_id": "4645344",
    "patient_id": "4534236",
    "clinic": "EPP",
    "station_id": "B2",
    "center": "ZDAP",
    "admission_date": date(2025, 12, 15),
    "discharge_date": date(2026, 1, 5),

    "honos_entry_total": 18,
    "honos_entry_date": date(2025, 12, 16),
    "honos_discharge_total": None,
    "honos_discharge_date": None,
    "honos_discharge_suicidality": None,

    "bscl_total_entry": 55,
    "bscl_entry_date": date(2025, 12, 16),
    "bscl_total_discharge": None,
    "bscl_discharge_date": None,
    "bscl_discharge_suicidality": None,

    "bfs_1": None, "bfs_2": None, "bfs_3": None,

    "isolations": []
  },

  # 4) Suizidalität hoch bei Austritt (HONOS >=3 oder BSCL >=3) => CRITICAL + Extra Info
  {
    "case_id": "4645345",
    "patient_id": "4534237",
    "clinic": "EPP",
    "station_id": "A1",
    "center": "ZAPE",
    "admission_date": date(2026, 1, 2),
    "discharge_date": date(2026, 1, 12),

    "honos_entry_total": 16,
    "honos_entry_date": date(2026, 1, 3),
    "honos_discharge_total": 15,
    "honos_discharge_date": date(2026, 1, 12),
    "honos_discharge_suicidality": 3,

    "bscl_total_entry": 48,
    "bscl_entry_date": date(2026, 1, 3),
    "bscl_total_discharge": 47,
    "bscl_discharge_date": date(2026, 1, 12),
    "bscl_discharge_suicidality": 2,

    "bfs_1": 7, "bfs_2": 8, "bfs_3": 9,

    "isolations": [
  { "start": "2026-01-10T08:00:00Z", "stop": None }
]
  },

  # 5) Isolation ohne Stop >48h => CRITICAL
  {
    "case_id": "4645346",
    "patient_id": "4534238",
    "clinic": "EPP",
    "station_id": "B0",
    "center": "ZDAP",
    "admission_date": date(2026, 1, 8),
    "discharge_date": None,

    "honos_entry_total": 22,
    "honos_entry_date": date(2026, 1, 9),
    "honos_discharge_total": None,
    "honos_discharge_date": None,
    "honos_discharge_suicidality": None,

    "bscl_total_entry": 60,
    "bscl_entry_date": date(2026, 1, 9),
    "bscl_total_discharge": None,
    "bscl_discharge_date": None,
    "bscl_discharge_suicidality": 3,

    "bfs_1": 1, "bfs_2": 2, "bfs_3": 3,

    "isolations": [
      {"start": "2026-01-10T08:00:00Z", "stop": None}
    ]
  },

  # 6) Mehrfach-Isolation (mehr als 1 Episode) => WARN, auch wenn alles sonst ok
  {
    "case_id": "4645347",
    "patient_id": "4534239",
    "clinic": "EPP",
    "station_id": "B2",
    "center": "ZDAP",
    "admission_date": date(2026, 1, 5),
    "discharge_date": None,

    "honos_entry_total": 10,
    "honos_entry_date": date(2026, 1, 6),
    "honos_discharge_total": None,
    "honos_discharge_date": None,
    "honos_discharge_suicidality": None,

    "bscl_total_entry": 35,
    "bscl_entry_date": date(2026, 1, 6),
    "bscl_total_discharge": None,
    "bscl_discharge_date": None,
    "bscl_discharge_suicidality": None,

    "bfs_1": 4, "bfs_2": 5, "bfs_3": 6,

    "isolations": [
      {"start": "2026-01-07T10:00:00Z", "stop": "2026-01-07T14:00:00Z"},
      {"start": "2026-01-09T12:00:00Z", "stop": "2026-01-09T15:00:00Z"}
    ]
  },
]



# Funktion: enrich_case – kapselt eine wiederverwendbare Backend-Operation.
def enrich_case(c: dict) -> dict:
    station_id = c["station_id"]
    center = STATION_CENTER.get(station_id, "UNKNOWN")
    clinic = c.get("clinic") or CLINIC_DEFAULT
    discharge_date: date | None = c.get("discharge_date")
    today = today_local()

    # --- BFS
    bfs_incomplete = any(c.get(k) is None for k in ("bfs_1", "bfs_2", "bfs_3"))

    # --- Eintritt: HONOS/BSCL Pflicht; Eskalation nach 3 Tagen
    honos_entry_total = c.get("honos_entry_total")
    bscl_entry_total = c.get("bscl_total_entry")
    days_since_admission = (today - c["admission_date"]).days

    honos_entry_missing_over_3d = honos_entry_total is None and days_since_admission > 3
    bscl_entry_missing_over_3d = bscl_entry_total is None and days_since_admission > 3

    # --- Austritt: Pflicht im ±3 Tage Fenster; CRITICAL wenn >3 Tage nach Austritt
    honos_discharge_total = c.get("honos_discharge_total")
    bscl_discharge_total = c.get("bscl_total_discharge")

    days_from_discharge: int | None = None
    if discharge_date is not None:
        days_from_discharge = (today - discharge_date).days

# Funktion: _due_missing – kapselt eine wiederverwendbare Backend-Operation.
    def _due_missing(total_val) -> bool:
        if discharge_date is None:
            return False
        if total_val is not None:
            return False
        if days_from_discharge is None:
            return False
        # within +/- 3 days around discharge date
        return abs(days_from_discharge) <= 3

    honos_discharge_due_missing = _due_missing(honos_discharge_total)
    bscl_discharge_due_missing = _due_missing(bscl_discharge_total)

    honos_discharge_missing_over_3d_after_discharge = (
        discharge_date is not None
        and honos_discharge_total is None
        and days_from_discharge is not None
        and days_from_discharge > 3
    )
    bscl_discharge_missing_over_3d_after_discharge = (
        discharge_date is not None
        and bscl_discharge_total is None
        and days_from_discharge is not None
        and days_from_discharge > 3
    )

    # --- Differenzen
    honos_delta = None
    if honos_entry_total is not None and honos_discharge_total is not None:
        honos_delta = honos_discharge_total - honos_entry_total

    bscl_delta = None
    if bscl_entry_total is not None and bscl_discharge_total is not None:
        bscl_delta = bscl_discharge_total - bscl_entry_total

    # --- Suizidalität bei Austritt
    suicidality_discharge_high = False
    if discharge_date is not None:
        h = c.get("honos_discharge_suicidality")
        b = c.get("bscl_discharge_suicidality")
        suicidality_discharge_high = (h is not None and h >= 3) or (b is not None and b >= 3)

    # --- Isolation
    isolations = c.get("isolations") or []
    isolation_multiple = len(isolations) > 1

    now_utc = datetime.now(timezone.utc)
    isolation_open_over_48h = False
    for ep in isolations:
        start = ep.get("start")
        stop = ep.get("stop")
        if not start:
            continue
        if stop is not None:
            continue
        try:
            start_dt = _parse_iso_dt(start)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if (now_utc - start_dt.astimezone(timezone.utc)).total_seconds() > 48 * 3600:
                isolation_open_over_48h = True
                break
        except Exception:
            continue

    out = dict(c)
    out["center"] = center
    out["clinic"] = clinic
    out["_derived"] = {
        # Eintritt
        "honos_entry_missing_over_3d": honos_entry_missing_over_3d,
        "bscl_entry_missing_over_3d": bscl_entry_missing_over_3d,

        # Austritt
        "honos_discharge_due_missing": honos_discharge_due_missing,
        "honos_discharge_missing_over_3d_after_discharge": honos_discharge_missing_over_3d_after_discharge,
        "bscl_discharge_due_missing": bscl_discharge_due_missing,
        "bscl_discharge_missing_over_3d_after_discharge": bscl_discharge_missing_over_3d_after_discharge,

        # Deltas
        "honos_delta": honos_delta,
        "bscl_delta": bscl_delta,

        # Suizidalität
        "suicidality_discharge_high": suicidality_discharge_high,

        # Isolation
        "isolation_open_over_48h": isolation_open_over_48h,
        "isolation_multiple": isolation_multiple,

        # BFS
        "bfs_incomplete": bfs_incomplete,
    }
    return out


# -----------------------------------------------------------------------------
# Rules (YAML)
# -----------------------------------------------------------------------------

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


# Funktion: load_rules – kapselt eine wiederverwendbare Backend-Operation.
def load_rules() -> dict:
    if RULES_PATH.exists():
        with RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # fallback rules
    return {
        "rules": [
            {
                "id": "HONOS_ENTRY_MISSING",
                "category": "completeness",
                "severity": "CRITICAL",
                "metric": "missing_honos_entry",
                "operator": "is_true",
                "value": True,
                "message": "HONOS Eintritt fehlt",
                "explanation": "Eintritts-HONOS ist noch nicht erfasst (Score 1–45).",
            },
            {
                "id": "HONOS_DISCHARGE_MISSING",
                "category": "completeness",
                "severity": "CRITICAL",
                "metric": "missing_honos_discharge",
                "operator": "is_true",
                "value": True,
                "message": "HONOS Austritt fehlt",
                "explanation": "Austritts-HONOS ist bei abgeschlossenem Fall noch nicht erfasst (Score 1–45).",
            },
            {
                "id": "BSCL_MISSING",
                "category": "completeness",
                "severity": "WARN",
                "metric": "missing_bscl",
                "operator": "is_true",
                "value": True,
                "message": "BSCL fehlt",
                "explanation": "BSCL wurde noch nicht erfasst.",
            },
            {
                "id": "BFS_INCOMPLETE",
                "category": "completeness",
                "severity": "WARN",
                "metric": "bfs_incomplete",
                "operator": "is_true",
                "value": True,
                "message": "BFS unvollständig",
                "explanation": "BFS Daten 1–3 müssen vollständig sein; mindestens ein Feld fehlt.",
            },
        ]
    }


# Funktion: seed_rule_definitions – kapselt eine wiederverwendbare Backend-Operation.
def seed_rule_definitions(db) -> None:
    """Seed Rules aus rules.yaml in die DB.

    WICHTIG:
      - Nur INSERT wenn rule_id noch nicht existiert.
      - Keine Überschreibung, damit Admin-Änderungen persistent bleiben.
    """
    try:
        rules = load_rules().get("rules", [])
    except Exception:
        rules = []

    if not isinstance(rules, list):
        return

    for r in rules:
        rid = r.get("id")
        if not rid:
            continue
        if db.get(RuleDefinition, rid) is not None:
            continue

        category = r.get("category") or "medical"
        severity = r.get("severity") or "WARN"
        metric = r.get("metric") or ""
        operator = r.get("operator") or ""
        expected = r.get("value")
        message = r.get("message") or rid
        explanation = r.get("explanation") or ""

        db.add(
            RuleDefinition(
                rule_id=rid,
                display_name=None,
                message=str(message),
                explanation=str(explanation),
                category=str(category),
                severity=str(severity),
                metric=str(metric),
                operator=str(operator),
                value_json=json.dumps(expected, ensure_ascii=False),
                enabled=True,
                is_system=True,
                updated_at=None,
                updated_by=None,
            )
        )
    db.commit()


# Funktion: load_rule_definitions – kapselt eine wiederverwendbare Backend-Operation.
def load_rule_definitions() -> list[RuleDefinition]:
    """Aktuelle Regeln aus DB. Falls leer (fresh DB), fall back auf YAML."""
    with SessionLocal() as db:
        rows = db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()
        if rows:
            return rows
        # Seed on-the-fly (sicher für fresh DBs)
        seed_rule_definitions(db)
        return db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()


# Funktion: eval_rule – kapselt eine wiederverwendbare Backend-Operation.
def eval_rule(metric_value, operator: str, value) -> bool:
    if operator == ">":
        return metric_value is not None and metric_value > value
    if operator == ">=":
        return metric_value is not None and metric_value >= value
    if operator == "is_null":
        return metric_value is None
    if operator == "is_true":
        return bool(metric_value) is True
    if operator == "is_false":
        return bool(metric_value) is False
    return False


# Funktion: evaluate_alerts – kapselt eine wiederverwendbare Backend-Operation.
def evaluate_alerts(case: dict) -> list[Alert]:
    rules = load_rule_definitions()
    derived = case.get("_derived") or {}

    alerts: list[Alert] = []
    for r in rules:
        if not r.enabled:
            continue

        category = r.category or "medical"
        metric = r.metric
        operator = r.operator
        try:
            expected = json.loads(r.value_json) if r.value_json is not None else None
        except Exception:
            expected = None

        if not metric or not operator:
            continue

        actual = derived.get(metric, case.get(metric))

        if eval_rule(actual, operator, expected):
            ch = compute_condition_hash(
                rule_id=r.rule_id,
                metric=metric,
                operator=operator,
                expected=expected,
                actual=actual,
                discharge_date=case.get("discharge_date"),
            )

            message = (r.display_name or r.message or r.rule_id)
            explanation = r.explanation or ""

            alerts.append(
                Alert(
                    rule_id=r.rule_id,
                    severity=r.severity,
                    category=category,
                    message=message,
                    explanation=explanation,
                    condition_hash=ch,
                )
            )
    return alerts


# Funktion: summarize_severity – kapselt eine wiederverwendbare Backend-Operation.
def summarize_severity(alerts: list[Alert]) -> tuple[Severity, Optional[str], int, int]:
    """Returns (severity, top_alert_text, critical_count, warn_count)."""
    critical = [a for a in alerts if a.severity == "CRITICAL"]
    warn = [a for a in alerts if a.severity == "WARN"]

    critical_count = len(critical)
    warn_count = len(warn)

    if critical_count:
        msg = critical[0].message if critical_count == 1 else f"{critical_count} kritische Alerts"
        return "CRITICAL", msg, critical_count, warn_count

    if warn_count:
        # Requirement: if multiple warnings, show count in overview
        msg = warn[0].message if warn_count == 1 else f"{warn_count} Warnungen"
        return "WARN", msg, critical_count, warn_count

    return "OK", None, 0, 0


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/health")
# Funktion: health – kapselt eine wiederverwendbare Backend-Operation.
def health():
    return {"status": "ok"}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/cases", response_model=list[CaseSummary])
# Funktion: list_cases – kapselt eine wiederverwendbare Backend-Operation.
def list_cases(
    view: Literal["all", "completeness", "medical"] = "all",
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):

    station_id = ctx.station_id
    station_cases = [enrich_case(c) for c in DUMMY_CASES if c["station_id"] == station_id]
    case_ids = [c["case_id"] for c in station_cases]

    # Tagesversion ("Vers") der Station. Acks sind nur gültig, wenn sie zur
    # aktuellen Version gehören.
    current_version = get_day_version(station_id=station_id)

    acks = ack_store.get_acks_for_cases(case_ids, station_id)

    case_level_acked_at: dict[str, str] = {}
    # rule_states_today[case_id][rule_id] = ack_row (ACK oder SHIFT)
    rule_states_today: dict[str, dict[str, Any]] = {}
    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            if _ack_is_valid_today(
                acked_at_iso=a.acked_at,
                business_date=getattr(a, "business_date", None),
                version=getattr(a, "version", None),
                current_version=current_version,
            ):
                case_level_acked_at[a.case_id] = a.acked_at
            continue
        if a.ack_scope == "rule" and _ack_is_valid_today(
            acked_at_iso=a.acked_at,
            business_date=getattr(a, "business_date", None),
            version=getattr(a, "version", None),
            current_version=current_version,
        ):
            rule_states_today.setdefault(a.case_id, {})[a.scope_id] = a

    out: list[CaseSummary] = []
    for c in station_cases:
        raw_alerts = evaluate_alerts(c)
        # Sicht-Filter auf Rule-Ebene
        if view != "all":
            raw_alerts = [a for a in raw_alerts if a.category == view]

        # Suppress rule-acked alerts for the rest of the day (until next business day)
        visible_alerts: list[Alert] = []
        for al in raw_alerts:
            arow = rule_states_today.get(c["case_id"], {}).get(al.rule_id)
            if not arow:
                visible_alerts.append(al)
                continue
            if getattr(arow, "condition_hash", None) == al.condition_hash:
                # acknowledged today -> hide
                continue
            # condition changed -> invalidate and show again
            ack_store.invalidate_rule_ack_if_mismatch(
                case_id=c["case_id"],
                station_id=station_id,
                rule_id=al.rule_id,
                current_hash=al.condition_hash,
            )
            visible_alerts.append(al)

        severity, top_alert, critical_count, warn_count = summarize_severity(visible_alerts)

        # Fall verschwindet aus der Liste, sobald er heute "Fall quittiert" wurde.
        # (Reset oder nächster Geschäftstag lassen ihn wieder erscheinen.)
        if case_level_acked_at.get(c["case_id"]):
            continue

        out.append(
            CaseSummary(
                case_id=c["case_id"],
                patient_id=c["patient_id"],
                clinic=c["clinic"],
                center=c["center"],
                station_id=c["station_id"],
                admission_date=c["admission_date"],
                discharge_date=c["discharge_date"],
                severity=severity,
                top_alert=top_alert,
                critical_count=critical_count,
                warn_count=warn_count,
                acked_at=case_level_acked_at.get(c["case_id"]),
            )
        )

    return out


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/cases/{case_id}", response_model=CaseDetail)
# Funktion: get_case – kapselt eine wiederverwendbare Backend-Operation.
def get_case(
    case_id: str,
    view: Literal["all", "completeness", "medical"] = "all",
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):

    raw = next((x for x in DUMMY_CASES if x["case_id"] == case_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")

    c = enrich_case(raw)
    if c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    raw_alerts = evaluate_alerts(c)
    if view != "all":
        raw_alerts = [a for a in raw_alerts if a.category == view]
    # map current hash for active rules
    current_hash: dict[str, str] = {a.rule_id: a.condition_hash for a in raw_alerts}

    # Tagesversion der Station (wichtig für Reset)
    current_version = get_day_version(station_id=ctx.station_id)

    acks = ack_store.get_acks_for_cases([case_id], ctx.station_id)
    acked_at: str | None = None
    # rule_id -> {state: 'ACK'|'SHIFT', ts: '...', shift_code?: 'a'|'b'|'c'}
    rule_states: dict[str, dict[str, Any]] = {}

    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            if _ack_is_valid_today(
                acked_at_iso=a.acked_at,
                business_date=getattr(a, "business_date", None),
                version=getattr(a, "version", None),
                current_version=current_version,
            ):
                acked_at = a.acked_at
            continue

        if a.ack_scope == "rule":
            ch = current_hash.get(a.scope_id)
            if not ch:
                # rule currently not active -> ignore
                continue

            if _ack_is_valid_today(
                acked_at_iso=a.acked_at,
                business_date=getattr(a, "business_date", None),
                version=getattr(a, "version", None),
                current_version=current_version,
            ) and a.condition_hash == ch:
                # gültig für heute: Alert ausblenden
                state = getattr(a, "action", None) or "ACK"
                rule_states[a.scope_id] = {
                    "state": state,
                    "ts": a.acked_at,
                    "shift_code": getattr(a, "shift_code", None),
                }
            elif a.condition_hash != ch:
                # condition changed -> invalidate once and show again
                ack_store.invalidate_rule_ack_if_mismatch(
                    case_id=case_id,
                    station_id=ctx.station_id,
                    rule_id=a.scope_id,
                    current_hash=ch,
                )

    # Suppress alerts that were acknowledged/shifted today (rule-level)
    visible_alerts = [a for a in raw_alerts if a.rule_id not in rule_states]
    severity, top_alert, critical_count, warn_count = summarize_severity(visible_alerts)

    return CaseDetail(
        case_id=c["case_id"],
        patient_id=c["patient_id"],
        clinic=c["clinic"],
        center=c["center"],
        station_id=c["station_id"],
        admission_date=c["admission_date"],
        discharge_date=c["discharge_date"],
        severity=severity,
        top_alert=top_alert,
        critical_count=critical_count,
        warn_count=warn_count,
        acked_at=acked_at,
        honos=c.get("honos_entry_total"),
        bscl=c.get("bscl_total_entry"),
        bfs_complete=not (c.get("_derived") or {}).get("bfs_incomplete", False),
        alerts=visible_alerts,
        rule_states=rule_states,
    )


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/debug/rules")
# Funktion: debug_rules – kapselt eine wiederverwendbare Backend-Operation.
def debug_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("debug:view")),
):
    rules = load_rules()
    return {
        "rules_path": str(RULES_PATH),
        "exists": RULES_PATH.exists(),
        "rules_count": len(rules.get("rules", [])),
        "rules_sample": rules.get("rules", [])[:10],
    }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/debug/eval/{case_id}")
# Funktion: debug_eval – kapselt eine wiederverwendbare Backend-Operation.
def debug_eval(
    case_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("debug:view")),
):
    raw = next((x for x in DUMMY_CASES if x["case_id"] == case_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")
    c = enrich_case(raw)
    alerts = evaluate_alerts(c)
    return {
        "case_id": case_id,
        "station_id": c["station_id"],
        "derived": c.get("_derived", {}),
        "alerts": [a.model_dump() for a in alerts],
    }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/debug/ack-events")
# Funktion: debug_ack_events – kapselt eine wiederverwendbare Backend-Operation.
def debug_ack_events(
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    case_id: str | None = None,
    _perm: None = Depends(require_permission("debug:view")),
):
    events = ack_store.list_events(station_id=ctx.station_id, case_id=case_id, limit=200)
    return [
        {
            "ts": e.ts,
            "case_id": e.case_id,
            "station_id": e.station_id,
            "ack_scope": e.ack_scope,
            "scope_id": e.scope_id,
            "event_type": e.event_type,
            "user_id": e.user_id,
            "payload": e.payload,
        }
        for e in events
    ]

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/meta/stations")
# Funktion: meta_stations – kapselt eine wiederverwendbare Backend-Operation.
def meta_stations(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    # Für Prototyp: aus Dummy-Cases ableiten
    stations = sorted({c["station_id"] for c in DUMMY_CASES})
    return {"stations": stations}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/meta/users")
# Funktion: meta_users – kapselt eine wiederverwendbare Backend-Operation.
def meta_users(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    from app.models import User, UserRole

    with SessionLocal() as db:
        users = db.query(User).filter(User.is_active == True).order_by(User.user_id.asc()).all()  # noqa: E712
        roles = db.query(UserRole).all()
        by_user: dict[str, set[str]] = {}
        for r in roles:
            if r.station_id == "*" or r.station_id == ctx.station_id:
                by_user.setdefault(r.user_id, set()).add(r.role_id)

        return {
            "users": [
                {"user_id": u.user_id, "roles": sorted(by_user.get(u.user_id, set()))}
                for u in users
            ]
        }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/meta/me")
# Funktion: meta_me – kapselt eine wiederverwendbare Backend-Operation.
def meta_me(
    ctx: AuthContext = Depends(get_auth_context),
):
    """Return the caller's effective roles/permissions for the current scope.

    Purpose: UI bootstrap (feature gating) without requiring any elevated meta permission.
    Scope resolution:
      - ctx is optional; if omitted, the auth layer resolves to global scope ("*").
      - callers can still send ?ctx=... or X-Scope-Ctx / X-Station-Id.
    """
    return {
        "user_id": ctx.user_id,
        "station_id": ctx.station_id,
        "roles": sorted(ctx.roles),
        "permissions": sorted(ctx.permissions),
        "break_glass": bool(ctx.is_break_glass),
    }

# -----------------------------------------------------------------------------
# Ack API
# -----------------------------------------------------------------------------

# Klasse: AckRequest – strukturiert Daten/Logik (z.B. Modelle, Services).
class AckRequest(BaseModel):
    case_id: str
    ack_scope: str = "case"   # 'case' | 'rule'
    scope_id: str = "*"       # '*' or rule_id
    comment: Optional[str] = None

    # NEW: Aktionstyp. Standard ist ACK.
    # Für "Schieben" nutzt das Frontend action='SHIFT' und shift_code='a'|'b'|'c'.
    action: Optional[Literal["ACK", "SHIFT"]] = "ACK"
    shift_code: Optional[Literal["a", "b", "c"]] = None


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/ack")
# Funktion: ack – kapselt eine wiederverwendbare Backend-Operation.
def ack(
    req: AckRequest,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("ack:write")),
):

    if req.ack_scope not in ("case", "rule"):
        raise HTTPException(status_code=400, detail="ack_scope must be 'case' or 'rule'")

    raw = next((x for x in DUMMY_CASES if x["case_id"] == req.case_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")

    c = enrich_case(raw)
    if c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    # --- Eingabevalidierung für SHIFT
    if (req.action or "ACK") == "SHIFT" and (req.shift_code not in ("a", "b", "c")):
        raise HTTPException(status_code=400, detail="SHIFT requires shift_code to be one of: a, b, c")

    # Tageskontext für diesen Request (Geschäftstag + aktuelle Tagesversion)
    business_date = today_local().isoformat()
    current_version = get_day_version(station_id=ctx.station_id)

    # Rule-ack/shift gate: nur möglich, wenn die Regel aktuell aktiv ist.
    # Wir speichern den current condition_hash, damit ein späterer Datenupdate
    # die Meldung automatisch wieder öffnen kann (AUTO_REOPEN), falls sich die
    # Bedingung geändert hat.
    condition_hash: str | None = None
    if req.ack_scope == "rule":
        alerts = evaluate_alerts(c)
        alert = next((a for a in alerts if a.rule_id == req.scope_id), None)
        if not alert:
            raise HTTPException(status_code=409, detail="Rule not currently active; cannot ack.")
        condition_hash = alert.condition_hash

    # Case-ack gate: der Fall darf nur quittiert werden, wenn alle Einzelmeldungen
    # für die aktuelle Sicht bereits erledigt sind (ACK oder SHIFT heute).
    if req.ack_scope == "case":
        # Wir betrachten den gesamten Fall (unabhängig von View-Filter), weil
        # "Fall quittieren" semantisch den kompletten To-Do-Stack abschließt.
        active_alerts = evaluate_alerts(c)
        if active_alerts:
            # Sammle gültige rule-states für heute.
            acks = ack_store.get_acks_for_cases([req.case_id], ctx.station_id)
            current_hash = {a.rule_id: a.condition_hash for a in active_alerts}
            handled: set[str] = set()
            for a in acks:
                if a.ack_scope != "rule":
                    continue
                if not _ack_is_valid_today(
                    acked_at_iso=a.acked_at,
                    business_date=getattr(a, "business_date", None),
                    version=getattr(a, "version", None),
                    current_version=current_version,
                ):
                    continue
                rid = a.scope_id
                if current_hash.get(rid) and getattr(a, "condition_hash", None) == current_hash[rid]:
                    handled.add(rid)

            missing = [a.rule_id for a in active_alerts if a.rule_id not in handled]
            if missing:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Fall kann erst quittiert werden, wenn alle Einzelmeldungen quittiert oder geschoben sind.",
                        "open_rules": missing,
                    },
                )

    ack_row = ack_store.upsert_ack(
        case_id=req.case_id,
        station_id=ctx.station_id,
        ack_scope=req.ack_scope,
        scope_id=req.scope_id,
        user_id=ctx.user_id,
        comment=req.comment,
        condition_hash=condition_hash,
        business_date=business_date,
        version=current_version,
        action=(req.action or "ACK"),
        shift_code=req.shift_code,
    )

    return {
        "case_id": ack_row.case_id,
        "station_id": ack_row.station_id,
        "ack_scope": ack_row.ack_scope,
        "scope_id": ack_row.scope_id,
        "acked": True,
        "acked_at": ack_row.acked_at,
        "acked_by": ack_row.acked_by,
        "condition_hash": getattr(ack_row, "condition_hash", None),
    }


# -----------------------------------------------------------------------------
# Reset/Version API
# -----------------------------------------------------------------------------

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/day_state")
# Funktion: get_day_state – kapselt eine wiederverwendbare Backend-Operation.
def get_day_state(
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Liefert die aktuelle Tagesversion ("Vers") für die Station des Users."""
    return {
        "station_id": ctx.station_id,
        "business_date": today_local().isoformat(),
        "version": get_day_version(station_id=ctx.station_id),
    }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/reset_today")
# Funktion: reset_today – kapselt eine wiederverwendbare Backend-Operation.
def reset_today(
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("reset:today")),
):
    """Inkrementiert die Tagesversion.

    Effekt:
      - Alle Acks (Fall/Regel/Shift) mit der alten Version werden ignoriert.
      - Dadurch erscheinen alle Fälle/Meldungen des Tages wieder.

    Zusätzlich schreiben wir ein Audit-Event in `ack_event`.
    """

    bdate = today_local().isoformat()
    with SessionLocal() as db:
        row = db.get(DayState, (ctx.station_id, bdate))
        if row is None:
            row = DayState(station_id=ctx.station_id, business_date=bdate, version=1)
            db.add(row)
            db.commit()
            db.refresh(row)

        old_v = int(row.version)
        row.version = old_v + 1
        db.add(row)

        # Audit: Reset ist ein stationsweiter Vorgang, kein einzelner Fall.
        # Wir speichern case_id='*' und ack_scope='station'.
        db.add(
            ack_store._insert_event(
                case_id="*",
                station_id=ctx.station_id,
                ack_scope="station",
                scope_id=bdate,
                event_type="RESET_DAY",
                user_id=ctx.user_id,
                payload={"business_date": bdate, "old_version": old_v, "new_version": int(row.version)},
            )
        )

        db.commit()

    return {
        "station_id": ctx.station_id,
        "business_date": bdate,
        "version": get_day_version(station_id=ctx.station_id),
    }


# -----------------------------------------------------------------------------
# Admin API (RBAC / Audit / Break-glass)
# -----------------------------------------------------------------------------

# Klasse: AdminUserCreate – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminUserCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    is_active: bool = True
    roles: list[AdminAssignRole] = Field(default_factory=list)

# Klasse: AdminUserUpdate – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None

# Klasse: AdminAssignRole – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminAssignRole(BaseModel):
    role_id: str
    station_id: str = "*"   # specific station or '*'


# Klasse: AdminPermissionCreate – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminPermissionCreate(BaseModel):
    perm_id: str = Field(..., min_length=1)
    description: Optional[str] = None


# Klasse: AdminPermissionUpdate – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminPermissionUpdate(BaseModel):
    description: Optional[str] = None


# Klasse: AdminRoleCreate – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminRoleCreate(BaseModel):
    role_id: str = Field(..., min_length=1)
    description: Optional[str] = None


# Klasse: AdminRoleUpdate – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminRoleUpdate(BaseModel):
    description: Optional[str] = None


# Klasse: AdminRolePermissions – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminRolePermissions(BaseModel):
    permissions: list[str] = Field(default_factory=list)


# Klasse: AdminRuleUpsert – strukturiert Daten/Logik (z.B. Modelle, Services).
class AdminRuleUpsert(BaseModel):
    rule_id: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    message: str
    explanation: str
    category: str = "medical"
    severity: Severity
    metric: str
    operator: str
    value: Any = None
    enabled: bool = True

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/admin/users")
# Funktion: admin_list_users – kapselt eine wiederverwendbare Backend-Operation.
def admin_list_users(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    from app.models import User, UserRole
    with SessionLocal() as db:
        users = db.query(User).order_by(User.user_id.asc()).all()
        roles = db.query(UserRole).all()
        by_user: dict[str, list[dict[str, str]]] = {}
        for r in roles:
            by_user.setdefault(r.user_id, []).append({"role_id": r.role_id, "station_id": r.station_id})
        return {
            "users": [
                {
                    "user_id": u.user_id,
                    "display_name": u.display_name,
                    "is_active": bool(u.is_active),
                    "created_at": u.created_at,
                    "roles": sorted(by_user.get(u.user_id, []), key=lambda x: (x["role_id"], x["station_id"])),
                }
                for u in users
            ]
        }

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/admin/users")
# Funktion: admin_create_user – kapselt eine wiederverwendbare Backend-Operation.
def admin_create_user(
    body: AdminUserCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User, UserRole, Role
    with SessionLocal() as db:
        if db.get(User, body.user_id) is not None:
            raise HTTPException(status_code=409, detail="user already exists")
        u = User(user_id=body.user_id.strip(), display_name=body.display_name, is_active=body.is_active, created_at=datetime.now(timezone.utc).isoformat())
        db.add(u)

        # optional: initial role assignments
        for ra in body.roles or []:
            rid = (ra.role_id or "").strip()
            st = (ra.station_id or "*").strip() or "*"
            if not rid:
                continue
            if db.get(Role, rid) is None:
                continue
            if db.get(UserRole, (u.user_id, rid, st)) is None:
                db.add(UserRole(user_id=u.user_id, role_id=rid, station_id=st, created_at=datetime.now(timezone.utc).isoformat(), created_by=ctx.user_id))

        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_USER_CREATE",
            target_type="user",
            target_id=u.user_id,
            success=True,
            details={"display_name": body.display_name, "is_active": body.is_active},
        )
        return {"user_id": u.user_id}

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.put("/api/admin/users/{user_id}")
# Funktion: admin_update_user – kapselt eine wiederverwendbare Backend-Operation.
def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User
    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="user not found")
        if body.display_name is not None:
            u.display_name = body.display_name
        if body.is_active is not None:
            u.is_active = bool(body.is_active)
        db.add(u)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_USER_UPDATE",
            target_type="user",
            target_id=user_id,
            success=True,
            details={"display_name": body.display_name, "is_active": body.is_active},
        )
        return {"ok": True}

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/admin/users/{user_id}/roles")
# Funktion: admin_assign_role – kapselt eine wiederverwendbare Backend-Operation.
def admin_assign_role(
    user_id: str,
    body: AdminAssignRole,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User, Role, UserRole
    with SessionLocal() as db:
        if db.get(User, user_id) is None:
            raise HTTPException(status_code=404, detail="user not found")
        if db.get(Role, body.role_id) is None:
            raise HTTPException(status_code=404, detail="role not found")
        key=(user_id, body.role_id, body.station_id)
        if db.get(UserRole, key) is None:
            db.add(UserRole(user_id=user_id, role_id=body.role_id, station_id=body.station_id, created_at=datetime.now(timezone.utc).isoformat(), created_by=ctx.user_id))
            db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_ASSIGN",
            target_type="user_role",
            target_id=":".join(key),
            success=True,
            details={"user_id": user_id, "role_id": body.role_id, "station_id": body.station_id},
        )
        return {"ok": True}

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.delete("/api/admin/users/{user_id}/roles/{role_id}/{station_id}")
# Funktion: admin_remove_role – kapselt eine wiederverwendbare Backend-Operation.
def admin_remove_role(
    user_id: str,
    role_id: str,
    station_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import UserRole
    with SessionLocal() as db:
        r = db.get(UserRole, (user_id, role_id, station_id))
        if r is None:
            raise HTTPException(status_code=404, detail="assignment not found")
        db.delete(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_REMOVE",
            target_type="user_role",
            target_id=":".join([user_id, role_id, station_id]),
            success=True,
        )
        return {"ok": True}

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/admin/roles")
# Funktion: admin_list_roles – kapselt eine wiederverwendbare Backend-Operation.
def admin_list_roles(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    from app.models import Role, RolePermission
    with SessionLocal() as db:
        roles = db.query(Role).order_by(Role.role_id.asc()).all()
        rp = db.query(RolePermission).all()
        by_role: dict[str, list[str]] = {}
        for row in rp:
            by_role.setdefault(row.role_id, []).append(row.perm_id)
        return {
            "roles": [
                {
                    "role_id": r.role_id,
                    "description": r.description,
                    "permissions": sorted(by_role.get(r.role_id, [])),
                    "is_system": bool(r.is_system),
                }
                for r in roles
            ]
        }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/admin/permissions")
# Funktion: admin_list_permissions – kapselt eine wiederverwendbare Backend-Operation.
def admin_list_permissions(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    from app.models import Permission
    with SessionLocal() as db:
        rows = db.query(Permission).order_by(Permission.perm_id.asc()).all()
        return {
            "permissions": [
                {"perm_id": p.perm_id, "description": p.description, "is_system": bool(p.is_system)}
                for p in rows
            ]
        }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/admin/permissions")
# Funktion: admin_create_permission – kapselt eine wiederverwendbare Backend-Operation.
def admin_create_permission(
    body: AdminPermissionCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Permission
    with SessionLocal() as db:
        pid = body.perm_id.strip()
        if db.get(Permission, pid) is not None:
            raise HTTPException(status_code=409, detail="permission already exists")
        db.add(Permission(perm_id=pid, description=body.description, is_system=False))
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_PERMISSION_CREATE",
            target_type="permission",
            target_id=pid,
            success=True,
            details={"description": body.description},
        )
        return {"perm_id": pid}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.put("/api/admin/permissions/{perm_id}")
# Funktion: admin_update_permission – kapselt eine wiederverwendbare Backend-Operation.
def admin_update_permission(
    perm_id: str,
    body: AdminPermissionUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Permission
    with SessionLocal() as db:
        p = db.get(Permission, perm_id)
        if p is None:
            raise HTTPException(status_code=404, detail="permission not found")
        if body.description is not None:
            p.description = body.description
        db.add(p)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_PERMISSION_UPDATE",
            target_type="permission",
            target_id=perm_id,
            success=True,
            details={"description": body.description},
        )
        return {"ok": True}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.delete("/api/admin/permissions/{perm_id}")
# Funktion: admin_delete_permission – kapselt eine wiederverwendbare Backend-Operation.
def admin_delete_permission(
    perm_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Permission, RolePermission
    with SessionLocal() as db:
        p = db.get(Permission, perm_id)
        if p is None:
            raise HTTPException(status_code=404, detail="permission not found")
        if bool(p.is_system):
            raise HTTPException(status_code=400, detail="cannot delete system permission")
        # remove mappings first
        db.query(RolePermission).filter(RolePermission.perm_id == perm_id).delete()
        db.delete(p)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_PERMISSION_DELETE",
            target_type="permission",
            target_id=perm_id,
            success=True,
        )
        return {"ok": True}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/admin/roles")
# Funktion: admin_create_role – kapselt eine wiederverwendbare Backend-Operation.
def admin_create_role(
    body: AdminRoleCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role
    with SessionLocal() as db:
        rid = body.role_id.strip()
        if db.get(Role, rid) is not None:
            raise HTTPException(status_code=409, detail="role already exists")
        db.add(Role(role_id=rid, description=body.description, is_system=False))
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_CREATE",
            target_type="role",
            target_id=rid,
            success=True,
            details={"description": body.description},
        )
        return {"role_id": rid}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.put("/api/admin/roles/{role_id}")
# Funktion: admin_update_role – kapselt eine wiederverwendbare Backend-Operation.
def admin_update_role(
    role_id: str,
    body: AdminRoleUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role
    with SessionLocal() as db:
        r = db.get(Role, role_id)
        if r is None:
            raise HTTPException(status_code=404, detail="role not found")
        if body.description is not None:
            r.description = body.description
        db.add(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_UPDATE",
            target_type="role",
            target_id=role_id,
            success=True,
            details={"description": body.description},
        )
        return {"ok": True}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.delete("/api/admin/roles/{role_id}")
# Funktion: admin_delete_role – kapselt eine wiederverwendbare Backend-Operation.
def admin_delete_role(
    role_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role, RolePermission, UserRole
    with SessionLocal() as db:
        r = db.get(Role, role_id)
        if r is None:
            raise HTTPException(status_code=404, detail="role not found")
        if bool(r.is_system):
            raise HTTPException(status_code=400, detail="cannot delete system role")
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        db.query(UserRole).filter(UserRole.role_id == role_id).delete()
        db.delete(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_DELETE",
            target_type="role",
            target_id=role_id,
            success=True,
        )
        return {"ok": True}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.put("/api/admin/roles/{role_id}/permissions")
# Funktion: admin_set_role_permissions – kapselt eine wiederverwendbare Backend-Operation.
def admin_set_role_permissions(
    role_id: str,
    body: AdminRolePermissions,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role, Permission, RolePermission
    with SessionLocal() as db:
        role = db.get(Role, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="role not found")
        if bool(role.is_system):
            raise HTTPException(status_code=400, detail="cannot edit system role permissions")

        desired = sorted({p.strip() for p in (body.permissions or []) if p and p.strip()})
        # validate permissions exist
        for pid in desired:
            if db.get(Permission, pid) is None:
                raise HTTPException(status_code=400, detail=f"unknown permission: {pid}")

        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        for pid in desired:
            db.add(RolePermission(role_id=role_id, perm_id=pid))
        db.commit()

        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_PERMISSIONS_SET",
            target_type="role",
            target_id=role_id,
            success=True,
            details={"permissions": desired},
        )
        return {"ok": True, "permissions": desired}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.delete("/api/admin/users/{user_id}")
# Funktion: admin_delete_user – kapselt eine wiederverwendbare Backend-Operation.
def admin_delete_user(
    user_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User, UserRole
    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="user not found")
        # prevent locking yourself out accidentally
        if u.user_id == ctx.user_id:
            raise HTTPException(status_code=400, detail="cannot delete own user")

        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        db.delete(u)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_USER_DELETE",
            target_type="user",
            target_id=user_id,
            success=True,
        )
        return {"ok": True}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/meta/rules")
# Funktion: meta_rules – kapselt eine wiederverwendbare Backend-Operation.
def meta_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    # read-only for all permitted clients
    with SessionLocal() as db:
        rows = db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()
        return {
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "display_name": r.display_name,
                    "message": r.message,
                    "explanation": r.explanation,
                    "category": r.category,
                    "severity": r.severity,
                    "metric": r.metric,
                    "operator": r.operator,
                    "value_json": r.value_json,
                    "enabled": bool(r.enabled),
                    "is_system": bool(r.is_system),
                    "updated_at": r.updated_at,
                    "updated_by": r.updated_by,
                }
                for r in rows
            ]
        }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/admin/rules")
# Funktion: admin_list_rules – kapselt eine wiederverwendbare Backend-Operation.
def admin_list_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    with SessionLocal() as db:
        rows = db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()
        return {
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "display_name": r.display_name,
                    "message": r.message,
                    "explanation": r.explanation,
                    "category": r.category,
                    "severity": r.severity,
                    "metric": r.metric,
                    "operator": r.operator,
                    "value_json": r.value_json,
                    "enabled": bool(r.enabled),
                    "is_system": bool(r.is_system),
                    "updated_at": r.updated_at,
                    "updated_by": r.updated_by,
                }
                for r in rows
            ]
        }


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.put("/api/admin/rules/{rule_id}")
# Funktion: admin_upsert_rule – kapselt eine wiederverwendbare Backend-Operation.
def admin_upsert_rule(
    rule_id: str,
    body: AdminRuleUpsert,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    if body.rule_id.strip() != rule_id.strip():
        raise HTTPException(status_code=400, detail="rule_id mismatch")

    # Hard guard: prevent unknown operator injection
    allowed_ops = {">", ">=", "is_null", "is_true", "is_false"}
    if body.operator not in allowed_ops:
        raise HTTPException(status_code=400, detail=f"unsupported operator: {body.operator}")

    with SessionLocal() as db:
        r = db.get(RuleDefinition, rule_id)
        if r is None:
            r = RuleDefinition(rule_id=rule_id, is_system=False)
            db.add(r)

        r.display_name = body.display_name
        r.message = body.message
        r.explanation = body.explanation
        r.category = body.category
        r.severity = body.severity
        r.metric = body.metric
        r.operator = body.operator
        r.value_json = json.dumps(body.value, ensure_ascii=False)
        r.enabled = bool(body.enabled)
        r.updated_at = datetime.now(timezone.utc).isoformat()
        r.updated_by = ctx.user_id
        db.add(r)
        db.commit()

        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_RULE_UPSERT",
            target_type="rule_definition",
            target_id=rule_id,
            success=True,
            details={
                "display_name": body.display_name,
                "message": body.message,
                "category": body.category,
                "severity": body.severity,
                "metric": body.metric,
                "operator": body.operator,
                "value": body.value,
                "enabled": body.enabled,
            },
        )
        return {"ok": True, "rule_id": rule_id}


# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.delete("/api/admin/rules/{rule_id}")
# Funktion: admin_delete_rule – kapselt eine wiederverwendbare Backend-Operation.
def admin_delete_rule(
    rule_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    with SessionLocal() as db:
        r = db.get(RuleDefinition, rule_id)
        if r is None:
            raise HTTPException(status_code=404, detail="rule not found")
        if bool(r.is_system):
            raise HTTPException(status_code=400, detail="cannot delete system rule")
        db.delete(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_RULE_DELETE",
            target_type="rule_definition",
            target_id=rule_id,
            success=True,
        )
        return {"ok": True}

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/admin/audit")
# Funktion: admin_audit – kapselt eine wiederverwendbare Backend-Operation.
def admin_audit(
    limit: int = 200,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("audit:read")),
):
    from app.models import SecurityEvent
    with SessionLocal() as db:
        rows = (
            db.query(SecurityEvent)
            .order_by(SecurityEvent.ts.desc())
            .limit(max(1, min(int(limit), 1000)))
            .all()
        )
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "ts": e.ts,
                    "actor_user_id": e.actor_user_id,
                    "actor_station_id": e.actor_station_id,
                    "action": e.action,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "success": bool(e.success),
                    "message": e.message,
                    "ip": e.ip,
                    "user_agent": e.user_agent,
                    "details": e.details,
                }
                for e in rows
            ]
        }

# Klasse: BreakGlassActivateReq – strukturiert Daten/Logik (z.B. Modelle, Services).
class BreakGlassActivateReq(BaseModel):
    reason: str = Field(..., min_length=5)
    duration_minutes: int = Field(default=60, ge=5, le=720)
    station_scope: str = Field(default="*")

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/break_glass/activate")
# Funktion: break_glass_activate – kapselt eine wiederverwendbare Backend-Operation.
def break_glass_activate(
    body: BreakGlassActivateReq,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("breakglass:activate")),
):
    with SessionLocal() as db:
        s = activate_break_glass(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            station_scope=body.station_scope,
            reason=body.reason,
            duration_minutes=body.duration_minutes,
        )
        return {"session_id": s.session_id, "expires_at": s.expires_at, "station_scope": s.station_id}

# Klasse: BreakGlassRevokeReq – strukturiert Daten/Logik (z.B. Modelle, Services).
class BreakGlassRevokeReq(BaseModel):
    review_note: Optional[str] = None

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.post("/api/admin/break_glass/{session_id}/revoke")
# Funktion: break_glass_revoke – kapselt eine wiederverwendbare Backend-Operation.
def break_glass_revoke(
    session_id: str,
    body: BreakGlassRevokeReq,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("breakglass:review")),
):
    with SessionLocal() as db:
        revoke_break_glass(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            session_id=session_id,
            review_note=body.review_note,
        )
    return {"ok": True}

# Route: HTTP-Endpoint – Auth/Permissions werden serverseitig geprüft (nicht nur im Frontend).
@app.get("/api/admin/break_glass")
# Funktion: break_glass_list – kapselt eine wiederverwendbare Backend-Operation.
def break_glass_list(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("breakglass:review")),
):
    from app.models import BreakGlassSession
    with SessionLocal() as db:
        rows = db.query(BreakGlassSession).order_by(BreakGlassSession.created_at.desc()).limit(200).all()
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "station_id": s.station_id,
                    "reason": s.reason,
                    "created_at": s.created_at,
                    "expires_at": s.expires_at,
                    "revoked_at": s.revoked_at,
                    "revoked_by": s.revoked_by,
                    "review_note": s.review_note,
                }
                for s in rows
            ]
        }
