"""Notification-Rules Endpoints."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth import AuthContext, get_auth_context
from app.rbac import require_permission
from app.audit import log_security_event
from app.schemas import NotificationRuleCreate, NotificationRuleUpdate
from app.db import SessionLocal
from app.models import NotificationRule, Case
from app.config import STATION_CENTER
from app.case_logic import get_station_cases
from app.rule_engine import evaluate_alerts

router = APIRouter()



@router.get("/api/admin/notifications")
def list_notification_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    """Alle Benachrichtigungsregeln auflisten."""
    with SessionLocal() as db:
        rules = db.query(NotificationRule).order_by(NotificationRule.id.asc()).all()
        return {
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "email": r.email,
                    "station_id": r.station_id,
                    "min_severity": r.min_severity,
                    "category": r.category,
                    "delay_minutes": r.delay_minutes,
                    "is_active": r.is_active,
                    "created_at": r.created_at,
                    "created_by": r.created_by,
                }
                for r in rules
            ]
        }


@router.post("/api/admin/notifications")
def create_notification_rule(
    body: NotificationRuleCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Neue Benachrichtigungsregel erstellen."""
    if body.min_severity not in ("WARN", "CRITICAL"):
        raise HTTPException(status_code=400, detail="min_severity muss WARN oder CRITICAL sein")
    with SessionLocal() as db:
        rule = NotificationRule(
            name=body.name,
            email=body.email,
            station_id=body.station_id or None,
            min_severity=body.min_severity,
            category=body.category or None,
            delay_minutes=body.delay_minutes,
            is_active=body.is_active,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=ctx.user_id,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="NOTIFICATION_RULE_CREATE",
            target_type="notification_rule", target_id=str(rule.id), success=True,
        )
        return {"ok": True, "id": rule.id}


@router.put("/api/admin/notifications/{rule_id}")
def update_notification_rule(
    rule_id: int,
    body: NotificationRuleUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Benachrichtigungsregel aktualisieren."""
    with SessionLocal() as db:
        rule = db.get(NotificationRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Regel nicht gefunden")
        if body.name is not None:
            rule.name = body.name
        if body.email is not None:
            rule.email = body.email
        if body.station_id is not None:
            rule.station_id = body.station_id or None
        if body.min_severity is not None:
            if body.min_severity not in ("WARN", "CRITICAL"):
                raise HTTPException(status_code=400, detail="min_severity muss WARN oder CRITICAL sein")
            rule.min_severity = body.min_severity
        if body.category is not None:
            rule.category = body.category or None
        if body.delay_minutes is not None:
            rule.delay_minutes = body.delay_minutes
        if body.is_active is not None:
            rule.is_active = body.is_active
        db.commit()
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="NOTIFICATION_RULE_UPDATE",
            target_type="notification_rule", target_id=str(rule_id), success=True,
        )
        return {"ok": True}


@router.delete("/api/admin/notifications/{rule_id}")
def delete_notification_rule(
    rule_id: int,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Benachrichtigungsregel löschen."""
    with SessionLocal() as db:
        rule = db.get(NotificationRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Regel nicht gefunden")
        db.delete(rule)
        db.commit()
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="NOTIFICATION_RULE_DELETE",
            target_type="notification_rule", target_id=str(rule_id), success=True,
        )
        return {"ok": True}


@router.get("/api/admin/notifications/pending")
def pending_notifications(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    """Zeigt an, welche Benachrichtigungen aktuell fällig wären.

    Nutzt die konfigurierten Regeln und prüft unquittierte Alerts.
    Versendet NOCH NICHTS (kein SMTP konfiguriert) — nur Preview.
    """
    with SessionLocal() as db:
        rules = db.query(NotificationRule).filter(NotificationRule.is_active == True).all()  # noqa

    if not rules:
        return {"pending": [], "note": "Keine aktiven Benachrichtigungsregeln konfiguriert."}

    # Alle Stationen laden
    with SessionLocal() as db:
        db_stations = db.query(Case.station_id).distinct().all()
        station_ids = sorted({s[0] for s in db_stations})

    pending = []
    for rule in rules:
        target_stations = [rule.station_id] if rule.station_id else station_ids
        for sid in target_stations:
            cases = get_station_cases(sid)
            for c in cases:
                alerts = evaluate_alerts(c)
                for alert in alerts:
                    # Filter: severity >= min_severity
                    if rule.min_severity == "CRITICAL" and alert.severity != "CRITICAL":
                        continue
                    # Filter: Kategorie
                    if rule.category and alert.category != rule.category:
                        continue
                    pending.append({
                        "rule_name": rule.name,
                        "email": rule.email,
                        "station_id": sid,
                        "case_id": c["case_id"],
                        "alert_rule_id": alert.rule_id,
                        "severity": alert.severity,
                        "message": alert.message,
                    })

    return {
        "pending": pending,
        "count": len(pending),
        "note": "Vorschau — SMTP noch nicht konfiguriert, kein Versand.",
    }
