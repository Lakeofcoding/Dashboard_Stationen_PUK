from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Optional

import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Dashboard Backend (MVP)", version="0.1.0")

# --- Models (API contract) ---

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


class CaseDetail(CaseSummary):
    honos: Optional[int] = None
    bscl: Optional[int] = None
    bfs_complete: bool = False
    alerts: list[Alert] = Field(default_factory=list)


# --- Dummy data (replace later with DB) ---

DUMMY_CASES: list[dict] = [
    {"case_id": "2026-0001", "station_id": "ST01", "admission_date": "2026-01-28", "discharge_date": None},
    {"case_id": "2026-0002", "station_id": "ST01", "admission_date": "2026-01-15", "discharge_date": None},
]

DUMMY_METRICS: dict[str, dict] = {
    "2026-0001": {"honos": 18, "bscl": None, "bfs_complete": False},
    "2026-0002": {"honos": 34, "bscl": 62, "bfs_complete": True},
}


# --- Rules: YAML (MVP: load once at startup) ---

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"

def get_rules_runtime() -> dict:
    # load fresh each time for debugging (and to avoid reload issues)
    return load_rules()



def load_rules() -> dict:
    if RULES_PATH.exists():
        with RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # fallback if file not there yet
    return {
        "rules": [
            {
                "id": "HONOS_HIGH",
                "severity": "CRITICAL",
                "metric": "honos",
                "operator": ">=",
                "value": 30,
                "message": "HONOS-Wert kritisch erhöht",
                "explanation": "HONOS ≥ 30 gilt als kritisch (MVP-Regel).",
            },
            {
                "id": "BSCL_MISSING",
                "severity": "WARN",
                "metric": "bscl",
                "operator": "is_null",
                "value": None,
                "message": "BSCL fehlt",
                "explanation": "BSCL wurde noch nicht erfasst (MVP-Regel).",
            },
        ]
    }




def eval_rule(metric_value, operator: str, value) -> bool:
    if operator == ">=":
        return metric_value is not None and metric_value >= value
    if operator == "is_null":
        return metric_value is None
    return False


def evaluate_alerts(metrics: dict) -> list[Alert]:
    rules = load_rules()  # <-- jedes Mal laden
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
        top = next(a.message for a in alerts if a.severity == "CRITICAL")
        return "CRITICAL", top
    if any(a.severity == "WARN" for a in alerts):
        top = next(a.message for a in alerts if a.severity == "WARN")
        return "WARN", top
    return "OK", None


# --- API endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/cases", response_model=list[CaseSummary])
def list_cases(station_id: str = "ST01"):
    # Placeholder "authorization": station_id parameter + hardcoded default
    results: list[CaseSummary] = []

    for c in DUMMY_CASES:
        if c["station_id"] != station_id:
            continue

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
            )
        )

    return results


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str):
    c = next((x for x in DUMMY_CASES if x["case_id"] == case_id), None)
    if c is None:
        # keep it simple for MVP; later proper HTTPException
        return CaseDetail(
            case_id=case_id,
            station_id="ST01",
            admission_date=date.today(),
            discharge_date=None,
            severity="OK",
            top_alert=None,
            honos=None,
            bscl=None,
            bfs_complete=False,
            alerts=[],
        )

    metrics = DUMMY_METRICS.get(case_id, {})
    alerts = evaluate_alerts(metrics)
    severity, top_alert = summarize_severity(alerts)

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
    )


@app.get("/api/debug/rules")
def debug_rules():
    rules = get_rules_runtime()
    return {
        "rules_path": str(RULES_PATH),
        "rules_loaded_keys": list(rules.keys()),
        "rules_count": len(rules.get("rules", [])),
        "rules_sample": rules.get("rules", [])[:2],
    }


@app.get("/api/debug/rules")
def debug_rules():
    rules = load_rules()
    return {
        "rules_path": str(RULES_PATH),
        "exists": RULES_PATH.exists(),
        "rules_loaded_keys": list(rules.keys()) if isinstance(rules, dict) else str(type(rules)),
        "rules_count": len(rules.get("rules", [])) if isinstance(rules, dict) else None,
        "rules_sample": (rules.get("rules", [])[:5] if isinstance(rules, dict) else None),
    }


@app.get("/api/debug/eval/{case_id}")
def debug_eval(case_id: str):
    metrics = DUMMY_METRICS.get(case_id, {})
    rules = load_rules()
    alerts = evaluate_alerts(metrics)
    return {
        "case_id": case_id,
        "metrics": metrics,
        "rules_count": len(rules.get("rules", [])) if isinstance(rules, dict) else None,
        "alerts": [a.model_dump() for a in alerts],
    }
