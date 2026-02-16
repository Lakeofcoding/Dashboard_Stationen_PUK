"""
Regel-Engine: Laden, Caching und Evaluation von Regeln.

Performance: Regeln werden fuer 60 Sekunden gecacht.
Bei 40 Stationen die alle 10s pollen, spart das ~240 DB-Queries/Minute.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from app.db import SessionLocal
from app.models import RuleDefinition
from app.schemas import Alert, Severity

# --- Pfad zu rules.yaml ---
RULES_PATH = Path(__file__).resolve().parent.parent.parent / "rules" / "rules.yaml"

# --- Cache ---
_rule_cache_lock = threading.Lock()
_rule_cache: list[RuleDefinition] = []
_rule_cache_ts: float = 0.0
_CACHE_TTL = 60.0  # Sekunden


def compute_condition_hash(
    *, rule_id: str, metric: str, operator: str, expected, actual,
    discharge_date: date | None,
) -> str:
    payload = {
        "rule_id": rule_id, "metric": metric, "operator": operator,
        "expected": expected, "actual": actual,
        "discharge_date": discharge_date.isoformat() if discharge_date else None,
        "ruleset_version": "v1",
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_rules_yaml() -> dict:
    """Laedt rules.yaml (mit Fallback auf eingebettete Basis-Regeln)."""
    if RULES_PATH.exists():
        with RULES_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "rules": [
            {"id": "HONOS_ENTRY_MISSING", "category": "completeness", "severity": "CRITICAL",
             "metric": "missing_honos_entry", "operator": "is_true", "value": True,
             "message": "HONOS Eintritt fehlt",
             "explanation": "Eintritts-HONOS ist noch nicht erfasst (Score 1-45)."},
            {"id": "HONOS_DISCHARGE_MISSING", "category": "completeness", "severity": "CRITICAL",
             "metric": "missing_honos_discharge", "operator": "is_true", "value": True,
             "message": "HONOS Austritt fehlt",
             "explanation": "Austritts-HONOS ist bei abgeschlossenem Fall noch nicht erfasst."},
            {"id": "BSCL_MISSING", "category": "completeness", "severity": "WARN",
             "metric": "missing_bscl", "operator": "is_true", "value": True,
             "message": "BSCL fehlt", "explanation": "BSCL wurde noch nicht erfasst."},
            {"id": "BFS_INCOMPLETE", "category": "completeness", "severity": "WARN",
             "metric": "bfs_incomplete", "operator": "is_true", "value": True,
             "message": "BFS unvollstaendig",
             "explanation": "BFS Daten 1-3 muessen vollstaendig sein."},
        ]
    }


def seed_rule_definitions(db) -> None:
    """Seed Rules aus rules.yaml in die DB (nur INSERT, kein UPDATE)."""
    try:
        rules = load_rules_yaml().get("rules", [])
    except Exception:
        rules = []
    if not isinstance(rules, list):
        return
    for r in rules:
        rid = r.get("id")
        if not rid or db.get(RuleDefinition, rid) is not None:
            continue
        db.add(RuleDefinition(
            rule_id=rid, display_name=None,
            message=str(r.get("message") or rid),
            explanation=str(r.get("explanation") or ""),
            category=str(r.get("category") or "medical"),
            severity=str(r.get("severity") or "WARN"),
            metric=str(r.get("metric") or ""),
            operator=str(r.get("operator") or ""),
            value_json=json.dumps(r.get("value"), ensure_ascii=False),
            enabled=True, is_system=True, updated_at=None, updated_by=None,
        ))
    db.commit()


def load_rule_definitions() -> list[RuleDefinition]:
    """Gecachte Regeln aus DB. TTL: 60s."""
    global _rule_cache, _rule_cache_ts
    now = time.time()
    if _rule_cache and (now - _rule_cache_ts) < _CACHE_TTL:
        return _rule_cache

    with _rule_cache_lock:
        # Double-check nach Lock
        if _rule_cache and (time.time() - _rule_cache_ts) < _CACHE_TTL:
            return _rule_cache
        with SessionLocal() as db:
            rows = db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()
            if not rows:
                seed_rule_definitions(db)
                rows = db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()
            # Detach from session
            for r in rows:
                db.expunge(r)
            _rule_cache = rows
            _rule_cache_ts = time.time()
    return _rule_cache


def invalidate_rule_cache():
    """Cache leeren (z.B. nach Admin-Aenderung an Regeln)."""
    global _rule_cache_ts
    _rule_cache_ts = 0.0


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
    """Evaluiert alle aktiven Regeln gegen einen angereicherten Fall."""
    rules = load_rule_definitions()
    derived = case.get("_derived") or {}
    alerts: list[Alert] = []

    for r in rules:
        if not r.enabled:
            continue
        metric = r.metric
        operator = r.operator
        if not metric or not operator:
            continue
        try:
            expected = json.loads(r.value_json) if r.value_json is not None else None
        except Exception:
            expected = None
        actual = derived.get(metric, case.get(metric))
        if eval_rule(actual, operator, expected):
            ch = compute_condition_hash(
                rule_id=r.rule_id, metric=metric, operator=operator,
                expected=expected, actual=actual,
                discharge_date=case.get("discharge_date"),
            )
            alerts.append(Alert(
                rule_id=r.rule_id, severity=r.severity,
                category=r.category or "medical",
                message=r.display_name or r.message or r.rule_id,
                explanation=r.explanation or "", condition_hash=ch,
            ))
    return alerts


def summarize_severity(alerts: list[Alert]) -> tuple[Severity, Optional[str], int, int]:
    """Returns (severity, top_alert_text, critical_count, warn_count)."""
    critical = [a for a in alerts if a.severity == "CRITICAL"]
    warn = [a for a in alerts if a.severity == "WARN"]
    cc, wc = len(critical), len(warn)
    if cc:
        msg = critical[0].message if cc == 1 else f"{cc} kritische Alerts"
        return "CRITICAL", msg, cc, wc
    if wc:
        msg = warn[0].message if wc == 1 else f"{wc} Warnungen"
        return "WARN", msg, cc, wc
    return "OK", None, 0, 0
