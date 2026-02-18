"""Case-Endpoints: Listing, Detail, ACK, Shift, DayState, Reset."""
from __future__ import annotations
from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import AuthContext, get_auth_context, require_ctx
from app.rbac import require_permission
from app.schemas import Alert, CaseSummary, CaseDetail
from app.day_state import today_local, get_day_version, ack_is_valid_today
from app.rule_engine import evaluate_alerts, summarize_severity
from app.case_logic import (
    get_station_cases, get_single_case, enrich_case, get_valid_shift_codes,
    build_parameter_status,
)
from app.ack_store import AckStore
from app.db import SessionLocal
from app.models import DayState, ShiftReason

ack_store = AckStore()


class AckRequest(BaseModel):
    case_id: str
    ack_scope: str = "case"
    scope_id: str = "*"
    comment: Optional[str] = None
    action: Optional[Literal["ACK", "SHIFT"]] = "ACK"
    shift_code: Optional[str] = None


router = APIRouter()



@router.get("/api/cases", response_model=list[CaseSummary])
def list_cases(
    view: Literal["all", "completeness", "medical"] = "all",
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):

    station_id = ctx.station_id
    station_cases = get_station_cases(station_id)
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
            if ack_is_valid_today(
                acked_at_iso=a.acked_at,
                business_date=getattr(a, "business_date", None),
                version=getattr(a, "version", None),
                current_version=current_version,
            ):
                case_level_acked_at[a.case_id] = a.acked_at
            continue
        if a.ack_scope == "rule" and ack_is_valid_today(
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
                parameter_status=build_parameter_status(c),
            )
        )

    return out


@router.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str,
    view: Literal["all", "completeness", "medical"] = "all",
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):

    raw = get_single_case(case_id)
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
            if ack_is_valid_today(
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

            if ack_is_valid_today(
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
        parameter_status=build_parameter_status(c),
        honos=c.get("honos_entry_total"),
        bscl=c.get("bscl_total_entry"),
        bfs_complete=not (c.get("_derived") or {}).get("bfs_incomplete", False),
        alerts=visible_alerts,
        rule_states=rule_states,
    )


@router.post("/api/ack")
def ack(
    req: AckRequest,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("ack:write")),
):

    if req.ack_scope not in ("case", "rule"):
        raise HTTPException(status_code=400, detail="ack_scope must be 'case' or 'rule'")

    raw = get_single_case(req.case_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")

    c = enrich_case(raw)
    if c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    # --- Eingabevalidierung für SHIFT
    if (req.action or "ACK") == "SHIFT":
        # Validate shift code against configured reasons
        valid_codes = _get_valid_shift_codes()
        if req.shift_code not in valid_codes:
            raise HTTPException(status_code=400, detail=f"SHIFT requires a valid shift_code. Valid: {', '.join(valid_codes)}")

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
                if not ack_is_valid_today(
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


@router.get("/api/day_state")
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


@router.post("/api/reset_today")
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


@router.get("/api/shift_reasons")
def list_shift_reasons(
    ctx: AuthContext = Depends(get_auth_context),
):
    """Gibt alle aktiven Schiebe-Gründe zurück (für Frontend)."""
    with SessionLocal() as db:
        reasons = db.query(ShiftReason).filter(ShiftReason.is_active == True).order_by(ShiftReason.sort_order).all()  # noqa: E712
        return {
            "reasons": [
                {
                    "id": r.id,
                    "code": r.code,
                    "label": r.label,
                    "description": r.description,
                }
                for r in reasons
            ]
        }
