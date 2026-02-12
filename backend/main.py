from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
import yaml
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from app.ack_store import AckStore
from app.auth import AuthContext, get_auth_context, require_role
from app.db import init_db

# -----------------------------------------------------------------------------
# Helpers: condition hash
# -----------------------------------------------------------------------------

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
def _startup():
    init_db()


# -----------------------------------------------------------------------------
# API models
# -----------------------------------------------------------------------------

Severity = Literal["OK", "WARN", "CRITICAL"]


def today_local() -> date:
    """Business date for acknowledgement expiry (Europe/Zurich)."""
    return datetime.now(ZoneInfo("Europe/Zurich")).date()


def _parse_iso_dt(s: str) -> datetime:
    # Handle trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _acked_today(acked_at_iso: str) -> bool:
    """Acks are only valid until the next business day."""
    try:
        dt = datetime.fromisoformat(acked_at_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return dt.astimezone(ZoneInfo("Europe/Zurich")).date() == today_local()


class Alert(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    explanation: str
    condition_hash: str


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


class CaseDetail(CaseSummary):
    # For UI convenience
    honos: Optional[int] = None
    bscl: Optional[int] = None
    bfs_complete: bool = False

    alerts: list[Alert] = Field(default_factory=list)

    # rule_id -> acked_at (only if ack is valid today + matches condition_hash)
    rule_acks: dict[str, str] = Field(default_factory=dict)


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


def load_rules() -> dict:
    if RULES_PATH.exists():
        with RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # fallback rules
    return {
        "rules": [
            {
                "id": "HONOS_ENTRY_MISSING",
                "severity": "CRITICAL",
                "metric": "missing_honos_entry",
                "operator": "is_true",
                "value": True,
                "message": "HONOS Eintritt fehlt",
                "explanation": "Eintritts-HONOS ist noch nicht erfasst (Score 1–45).",
            },
            {
                "id": "HONOS_DISCHARGE_MISSING",
                "severity": "CRITICAL",
                "metric": "missing_honos_discharge",
                "operator": "is_true",
                "value": True,
                "message": "HONOS Austritt fehlt",
                "explanation": "Austritts-HONOS ist bei abgeschlossenem Fall noch nicht erfasst (Score 1–45).",
            },
            {
                "id": "BSCL_MISSING",
                "severity": "WARN",
                "metric": "missing_bscl",
                "operator": "is_true",
                "value": True,
                "message": "BSCL fehlt",
                "explanation": "BSCL wurde noch nicht erfasst.",
            },
            {
                "id": "BFS_INCOMPLETE",
                "severity": "WARN",
                "metric": "bfs_incomplete",
                "operator": "is_true",
                "value": True,
                "message": "BFS unvollständig",
                "explanation": "BFS Daten 1–3 müssen vollständig sein; mindestens ein Feld fehlt.",
            },
        ]
    }


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


def evaluate_alerts(case: dict) -> list[Alert]:
    rules = load_rules()
    derived = case.get("_derived") or {}

    alerts: list[Alert] = []
    for r in rules.get("rules", []):
        metric = r.get("metric")
        operator = r.get("operator")
        expected = r.get("value")

        if not metric or not operator:
            continue

        actual = derived.get(metric, case.get(metric))

        if eval_rule(actual, operator, expected):
            ch = compute_condition_hash(
                rule_id=r["id"],
                metric=metric,
                operator=operator,
                expected=expected,
                actual=actual,
                discharge_date=case.get("discharge_date"),
            )
            alerts.append(
                Alert(
                    rule_id=r["id"],
                    severity=r["severity"],
                    message=r["message"],
                    explanation=r["explanation"],
                    condition_hash=ch,
                )
            )
    return alerts


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

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/cases", response_model=list[CaseSummary])
def list_cases(ctx: AuthContext = Depends(get_auth_context)):
    require_role(ctx, "VIEW_DASHBOARD")

    station_id = ctx.station_id
    station_cases = [enrich_case(c) for c in DUMMY_CASES if c["station_id"] == station_id]
    case_ids = [c["case_id"] for c in station_cases]

    acks = ack_store.get_acks_for_cases(case_ids, station_id)

    case_level_acked_at: dict[str, str] = {}
    # rule_acks_today[case_id][rule_id] = ack_row
    rule_acks_today: dict[str, dict[str, Any]] = {}
    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            case_level_acked_at[a.case_id] = a.acked_at
            continue
        if a.ack_scope == "rule" and _acked_today(a.acked_at):
            rule_acks_today.setdefault(a.case_id, {})[a.scope_id] = a

    out: list[CaseSummary] = []
    for c in station_cases:
        raw_alerts = evaluate_alerts(c)

        # Suppress rule-acked alerts for the rest of the day (until next business day)
        visible_alerts: list[Alert] = []
        for al in raw_alerts:
            arow = rule_acks_today.get(c["case_id"], {}).get(al.rule_id)
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

        # fall out if ended AND case-acked
        if c.get("discharge_date") is not None and case_level_acked_at.get(c["case_id"]):
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


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, ctx: AuthContext = Depends(get_auth_context)):
    require_role(ctx, "VIEW_DASHBOARD")

    raw = next((x for x in DUMMY_CASES if x["case_id"] == case_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")

    c = enrich_case(raw)
    if c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    raw_alerts = evaluate_alerts(c)
    # map current hash for active rules
    current_hash: dict[str, str] = {a.rule_id: a.condition_hash for a in raw_alerts}

    acks = ack_store.get_acks_for_cases([case_id], ctx.station_id)
    acked_at: str | None = None
    rule_acks: dict[str, str] = {}

    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            acked_at = a.acked_at
            continue

        if a.ack_scope == "rule":
            ch = current_hash.get(a.scope_id)
            if not ch:
                # rule currently not active -> ignore
                continue

            if _acked_today(a.acked_at) and a.condition_hash == ch:
                # valid only for today; hides the alert
                rule_acks[a.scope_id] = a.acked_at
            elif a.condition_hash != ch:
                # condition changed -> invalidate once and show again
                ack_store.invalidate_rule_ack_if_mismatch(
                    case_id=case_id,
                    station_id=ctx.station_id,
                    rule_id=a.scope_id,
                    current_hash=ch,
                )

    # Suppress alerts that were acknowledged today (rule-level)
    visible_alerts = [a for a in raw_alerts if a.rule_id not in rule_acks]
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
        rule_acks=rule_acks,
    )


@app.get("/api/debug/rules")
def debug_rules():
    rules = load_rules()
    return {
        "rules_path": str(RULES_PATH),
        "exists": RULES_PATH.exists(),
        "rules_count": len(rules.get("rules", [])),
        "rules_sample": rules.get("rules", [])[:10],
    }


@app.get("/api/debug/eval/{case_id}")
def debug_eval(case_id: str, ctx: AuthContext = Depends(get_auth_context)):
    require_role(ctx, "VIEW_DASHBOARD")
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


@app.get("/api/debug/ack-events")
def debug_ack_events(ctx: AuthContext = Depends(get_auth_context), case_id: str | None = None):
    require_role(ctx, "VIEW_DASHBOARD")
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

@app.get("/api/meta/stations")
def meta_stations(ctx: AuthContext = Depends(get_auth_context)):
    # Für Prototyp: aus Dummy-Cases ableiten
    stations = sorted({c["station_id"] for c in DUMMY_CASES})
    return {"stations": stations}

@app.get("/api/meta/users")
def meta_users(ctx: AuthContext = Depends(get_auth_context)):
    # Prototyp: fixe Demo-User; später: aus SSO/KISIM
    return {
        "users": [
            {"user_id": "demo", "roles": ["VIEW_DASHBOARD", "ACK_ALERT"]},
            {"user_id": "pflege1", "roles": ["VIEW_DASHBOARD"]},
            {"user_id": "arzt1", "roles": ["VIEW_DASHBOARD", "ACK_ALERT"]},
            {"user_id": "manager1", "roles": ["VIEW_DASHBOARD", "ACK_ALERT"]},
        ]
    }

# -----------------------------------------------------------------------------
# Ack API
# -----------------------------------------------------------------------------

class AckRequest(BaseModel):
    case_id: str
    ack_scope: str = "case"   # 'case' | 'rule'
    scope_id: str = "*"       # '*' or rule_id
    comment: Optional[str] = None


@app.post("/api/ack")
def ack(req: AckRequest, ctx: AuthContext = Depends(get_auth_context)):
    require_role(ctx, "ACK_ALERT")

    if req.ack_scope not in ("case", "rule"):
        raise HTTPException(status_code=400, detail="ack_scope must be 'case' or 'rule'")

    raw = next((x for x in DUMMY_CASES if x["case_id"] == req.case_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")

    c = enrich_case(raw)
    if c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    # Case-ack gate: only after discharge
    if req.ack_scope == "case" and c.get("discharge_date") is None:
        raise HTTPException(
            status_code=409,
            detail="Case cannot be acked before discharge/transfer is completed (discharge_date is null).",
        )

    # Rule-ack gate: only if rule is currently active; store current condition_hash
    condition_hash: str | None = None
    if req.ack_scope == "rule":
        alerts = evaluate_alerts(c)
        alert = next((a for a in alerts if a.rule_id == req.scope_id), None)
        if not alert:
            raise HTTPException(status_code=409, detail="Rule not currently active; cannot ack.")
        condition_hash = alert.condition_hash

    ack_row = ack_store.upsert_ack(
        case_id=req.case_id,
        station_id=ctx.station_id,
        ack_scope=req.ack_scope,
        scope_id=req.scope_id,
        user_id=ctx.user_id,
        comment=req.comment,
        condition_hash=condition_hash,
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
