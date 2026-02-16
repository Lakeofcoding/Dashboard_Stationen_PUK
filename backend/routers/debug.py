"""Debug-Endpoints (nur mit debug:view Permission)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.auth import AuthContext, get_auth_context, require_ctx
from app.rbac import require_permission
from app.case_logic import get_single_case, enrich_case
from app.rule_engine import evaluate_alerts, load_rules_yaml, RULES_PATH
from app.ack_store import AckStore
from app.db import SessionLocal
from app.models import Ack, AckEvent

ack_store = AckStore()

router = APIRouter()



@router.get("/api/debug/rules")
def debug_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("debug:view")),
):
    rules = load_rules_yaml()
    return {
        "rules_path": str(RULES_PATH),
        "exists": RULES_PATH.exists(),
        "rules_count": len(rules.get("rules", [])),
        "rules_sample": rules.get("rules", [])[:10],
    }


@router.get("/api/debug/eval/{case_id}")
def debug_eval(
    case_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("debug:view")),
):
    raw = get_single_case(case_id)
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


@router.get("/api/debug/ack-events")
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
