from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Optional

import yaml
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import init_db
from app.auth import AuthContext, get_auth_context, require_role
from app.ack_store import AckStore

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------

app = FastAPI(title="Dashboard Backend (MVP)", version="0.1.0")
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


class CaseSummary(BaseModel):
    case_id: str
    station_id: str
    admission_date: date
    discharge_date: Optional[date] = None
    severity: Severity
    top_alert: Optional[str] = None
    acked_at: Optional[str] = None


class CaseDetail(CaseSummary):
    honos: Optional[int] = None
    bscl: Optional[int] = None
    bfs_complete: bool = False
    alerts: list[Alert] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Dummy data (replace later by DB / KIS / KISIM)
# -----------------------------------------------------------------------------

DUMMY_CASES: list[dict] = [
    {"case_id": "2026-0001", "station_id": "ST01", "admission_date": date(2026, 1, 28), "discharge_date": None},
    {"case_id": "2026-0002", "station_id": "ST01", "admission_date": date(2026, 1, 15), "discharge_date": None},
]

DUMMY_METRICS: dict[str, dict] = {
    "2026-0001": {"honos": 18, "bscl": None, "bfs_complete": False},
    "2026-0002": {"honos": 34, "bscl": 62, "bfs_complete": True},
}


# -----------------------------------------------------------------------------
# Rules (YAML)
# -----------------------------------------------------------------------------

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


def load_rules() -> dict:
    if RULES_PATH.exists():
        with RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {"rules": []}


def eval_rule(metric_value, operator: str, value) -> bool:
    if operator == ">=":
        return metric_value is not None and metric_value >= value
    if operator == "is_null":
        return metric_value is None
    return False


def evaluate_alerts(metrics: dict) -> list[Alert]:
    rules = load_rules()
    alerts: list[Alert] = []

    for r in rules.get("rules", []):
        metric = r.get("metric")
        operator = r.get("operator")
        value = r.get("value")

        if metric is None or operator is None:
            continue

        metric_value = metrics.get(metric)

        if eval_rule(metric_value, operator, value):
            alerts.append(
                Alert(
                    rule_id=r["id"],
                    severity=r["severity"],
                    message=r["message"],
                    explanation=r["explanation"],
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

    station_cases = [c for c in DUMMY_CASES if c["station_id"] == ctx.station_id]
    case_ids = [c["case_id"] for c in station_cases]

    acks = ack_store.get_acks_for_cases(case_ids, ctx.station_id)
    case_level_acks: dict[str, str] = {}

    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            case_level_acks[a.case_id] = a.acked_at

    results: list[CaseSummary] = []

    for c in station_cases:
        metrics = DUMMY_METRICS.get(c["case_id"], {})
        alerts = evaluate_alerts(metrics)
        severity, top_alert = summarize_severity(alerts)

        results.append(
            CaseSummary(
                case_id=c["case_id"],
                station_id=c["station_id"],
                admission_date=c["admission_date"],
                discharge_date=c["discharge_date"],
                severity=severity,
                top_alert=top_alert,
                acked_at=case_level_acks.get(c["case_id"]),
            )
        )
    return results


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, ctx: AuthContext = Depends(get_auth_context)):
    require_role(ctx, "VIEW_DASHBOARD")

    c = next((x for x in DUMMY_CASES if x["case_id"] == case_id), None)
    if c is None or c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    metrics = DUMMY_METRICS.get(case_id, {})
    alerts = evaluate_alerts(metrics)
    severity, top_alert = summarize_severity(alerts)

    acks = ack_store.get_acks_for_cases([case_id], ctx.station_id)
    acked_at = None
    for a in acks:
        if a.ack_scope == "case" and a.scope_id == "*":
            acked_at = a.acked_at
            break

    return CaseDetail(
        case_id=c["case_id"],
        station_id=c["station_id"],
        admission_date=c["admission_date"],
        discharge_date=c["discharge_date"],
        severity=severity,
        top_alert=top_alert,
        honos=metrics.get("honos"),
        bscl=metrics.get("bscl"),
        bfs_complete=bool(metrics.get("bfs_complete", False)),
        alerts=alerts,
        acked_at=acked_at,
    )


# -----------------------------------------------------------------------------
# Debug
# -----------------------------------------------------------------------------

@app.get("/api/debug/rules")
def debug_rules():
    rules = load_rules()
    return {
        "rules_path": str(RULES_PATH),
        "exists": RULES_PATH.exists(),
        "rules_count": len(rules.get("rules", [])),
        "rules_sample": rules.get("rules", [])[:5],
    }


@app.get("/api/debug/eval/{case_id}")
def debug_eval(case_id: str):
    metrics = DUMMY_METRICS.get(case_id, {})
    alerts = evaluate_alerts(metrics)
    return {
        "case_id": case_id,
        "metrics": metrics,
        "alerts": [a.model_dump() for a in alerts],
    }


# -----------------------------------------------------------------------------
# Ack
# -----------------------------------------------------------------------------

class AckRequest(BaseModel):
    case_id: str
    ack_scope: str = "case"   # 'case' | 'rule'
    scope_id: str = "*"       # '*' oder rule_id
    comment: Optional[str] = None


@app.post("/api/ack")
def ack(req: AckRequest, ctx: AuthContext = Depends(get_auth_context)):
    require_role(ctx, "ACK_ALERT")

    if req.ack_scope not in ("case", "rule"):
        raise HTTPException(status_code=400, detail="ack_scope must be 'case' or 'rule'")

    ack_row = ack_store.upsert_ack(
        case_id=req.case_id,
        station_id=ctx.station_id,
        ack_scope=req.ack_scope,
        scope_id=req.scope_id,
        user_id=ctx.user_id,
        comment=req.comment,
    )

    return {
        "case_id": ack_row.case_id,
        "station_id": ack_row.station_id,
        "ack_scope": ack_row.ack_scope,
        "scope_id": ack_row.scope_id,
        "acked": True,
        "acked_at": ack_row.acked_at,
        "acked_by": ack_row.acked_by,
    }
