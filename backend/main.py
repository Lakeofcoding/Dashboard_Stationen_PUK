from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import yaml
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

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

    # case-level ack ("Fall vollständig") – only possible after discharge
    acked_at: Optional[str] = None


class CaseDetail(CaseSummary):
    honos_entry: Optional[int] = None
    honos_discharge: Optional[int] = None
    bscl: Optional[int] = None

    bfs_1: Optional[int] = None
    bfs_2: Optional[int] = None
    bfs_3: Optional[int] = None

    alerts: list[Alert] = Field(default_factory=list)

    # rule_id -> acked_at (only if ack is valid for current condition_hash)
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

DUMMY_CASES: list[dict] = [
    {
        "case_id": "4645342",
        "patient_id": "4534234",
        "clinic": "EPP",
        "station_id": "A1",
        "admission_date": date(2026, 1, 20),
        "discharge_date": None,
        "honos_entry": None,
        "honos_discharge": None,
        "bscl": 44,
        "bfs_1": None,
        "bfs_2": None,
        "bfs_3": None,
    },
    {
        "case_id": "4645343",
        "patient_id": "4534235",
        "clinic": "EPP",
        "station_id": "B0",
        "admission_date": date(2026, 1, 10),
        "discharge_date": None,
        "honos_entry": 21,
        "honos_discharge": None,
        "bscl": 62,
        "bfs_1": 12,
        "bfs_2": None,
        "bfs_3": None,
    },
    {
        "case_id": "4645344",
        "patient_id": "4534236",
        "clinic": "EPP",
        "station_id": "B2",
        "admission_date": date(2025, 12, 15),
        "discharge_date": date(2026, 1, 25),
        "honos_entry": 28,
        "honos_discharge": None,
        "bscl": 55,
        "bfs_1": 10,
        "bfs_2": 9,
        "bfs_3": 8,
    },
    {
        "case_id": "4645345",
        "patient_id": "4534237",
        "clinic": "EPP",
        "station_id": "A1",
        "admission_date": date(2025, 12, 1),
        "discharge_date": date(2026, 1, 10),
        "honos_entry": 18,
        "honos_discharge": 14,
        "bscl": 40,
        "bfs_1": 11,
        "bfs_2": 12,
        "bfs_3": 10,
    },
]


def enrich_case(c: dict) -> dict:
    station_id = c["station_id"]
    center = STATION_CENTER.get(station_id, "UNKNOWN")
    clinic = c.get("clinic") or CLINIC_DEFAULT
    discharge_date = c.get("discharge_date")

    missing_honos_entry = c.get("honos_entry") is None
    missing_honos_discharge = discharge_date is not None and c.get("honos_discharge") is None
    missing_bscl = c.get("bscl") is None
    bfs_incomplete = any(c.get(k) is None for k in ("bfs_1", "bfs_2", "bfs_3"))

    out = dict(c)
    out["center"] = center
    out["clinic"] = clinic
    out["_derived"] = {
        "missing_honos_entry": missing_honos_entry,
        "missing_honos_discharge": missing_honos_discharge,
        "missing_bscl": missing_bscl,
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


def summarize_severity(alerts: list[Alert]) -> tuple[Severity, Optional[str]]:
    if any(a.severity == "CRITICAL" for a in alerts):
        return "CRITICAL", next(a.message for a in alerts if a.severity == "CRITICAL")
    if any(a.severity == "WARN" for a in alerts):
        return "WARN", next(a.message for a in alerts if a.severity == "WARN")
    return "OK", None


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
    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            case_level_acked_at[a.case_id] = a.acked_at

    out: list[CaseSummary] = []
    for c in station_cases:
        alerts = evaluate_alerts(c)
        severity, top_alert = summarize_severity(alerts)

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

    alerts = evaluate_alerts(c)
    severity, top_alert = summarize_severity(alerts)

    # map current hash for active rules
    current_hash: dict[str, str] = {a.rule_id: a.condition_hash for a in alerts}

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
                # rule currently not active -> ignore in UI
                continue

            if a.condition_hash == ch:
                rule_acks[a.scope_id] = a.acked_at
            else:
                # invalidate once and write AUTO_REOPEN event
                ack_store.invalidate_rule_ack_if_mismatch(
                    case_id=case_id,
                    station_id=ctx.station_id,
                    rule_id=a.scope_id,
                    current_hash=ch,
                )

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
        acked_at=acked_at,
        honos_entry=c.get("honos_entry"),
        honos_discharge=c.get("honos_discharge"),
        bscl=c.get("bscl"),
        bfs_1=c.get("bfs_1"),
        bfs_2=c.get("bfs_2"),
        bfs_3=c.get("bfs_3"),
        alerts=alerts,
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
