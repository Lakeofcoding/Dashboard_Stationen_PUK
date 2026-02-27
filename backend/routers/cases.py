"""Case-Endpoints: Listing, Detail, ACK, Shift, DayState, Reset."""
from __future__ import annotations
import re
from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Path
from app.auth import AuthContext, get_auth_context, require_ctx
from app.rbac import require_permission
from app.schemas import Alert, CaseSummary, CaseDetail, AckRequest
from app.day_state import today_local, get_day_version, ack_is_valid_today
from app.rule_engine import evaluate_alerts, summarize_severity
from app.case_logic import (
    get_station_cases, get_single_case, enrich_case, get_valid_shift_codes,
    build_parameter_status, build_parameter_groups, build_langlieger_status, build_fu_status,
)
from app.excel_loader import get_lab_history, get_ekg_history, get_efm_events
from app.ack_store import AckStore
from app.db import SessionLocal
from app.models import Case, DayState, ShiftReason
from app.audit import log_security_event

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def _validate_case_id(case_id: str) -> str:
    """Validiert case_id: max 64 Zeichen, nur alphanumerisch + _.-"""
    if not _CASE_ID_RE.match(case_id):
        raise HTTPException(status_code=400, detail="Ungültige case_id (max 64 Zeichen, nur A-Z, 0-9, _, ., -)")
    return case_id


ack_store = AckStore()


router = APIRouter()


@router.get("/api/cases/browse", response_model=list[CaseSummary])
def browse_cases(
    clinic: Optional[str] = Query(default=None, description="Filter by clinic (e.g. EPP)"),
    center: Optional[str] = Query(default=None, description="Filter by center (e.g. ZAPE)"),
    station: Optional[str] = Query(default=None, description="Filter by station (e.g. Station G0)"),
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Alle Fälle über mehrere Stationen, gefiltert nach User-Scope.

    Server filtert automatisch auf sichtbare Stationen des Users.
    Ohne Filter: alle sichtbaren Fälle.
    """
    from app.rbac import get_user_visible_stations

    with SessionLocal() as db:
        # Sichtbare Stationen für diesen User
        visible = get_user_visible_stations(db, ctx.user_id)
        q = db.query(Case.station_id).distinct()
        station_ids = sorted({s[0] for s in q.all()})

    # RBAC-Filter: nur sichtbare Stationen
    if visible is not None:
        station_ids = [s for s in station_ids if s in visible]

    all_cases: list[CaseSummary] = []
    for sid in station_ids:
        cases = get_station_cases(sid)
        for c in cases:
            # Filter anwenden
            if clinic and c.get("clinic") != clinic:
                continue
            if center and c.get("center") != center:
                continue
            if station and c.get("station_id") != station:
                continue

            alerts = evaluate_alerts(c)
            sev, top_alert, cc, wc = summarize_severity(alerts)
            comp_alerts = [a for a in alerts if a.category == "completeness"]
            med_alerts = [a for a in alerts if a.category == "medical"]
            comp_sev, _, comp_cc, comp_wc = summarize_severity(comp_alerts)
            med_sev, _, med_cc, med_wc = summarize_severity(med_alerts)

            all_cases.append(CaseSummary(
                case_id=c["case_id"],
                patient_id=c["patient_id"],
                clinic=c.get("clinic", "UNKNOWN"),
                center=c.get("center", "UNKNOWN"),
                station_id=c["station_id"],
                admission_date=c["admission_date"],
                discharge_date=c.get("discharge_date"),
                severity=sev,
                top_alert=top_alert,
                critical_count=cc,
                warn_count=wc,
                completeness_severity=comp_sev,
                completeness_critical=comp_cc,
                completeness_warn=comp_wc,
                medical_severity=med_sev,
                medical_critical=med_cc,
                medical_warn=med_wc,
                case_status=c.get("case_status"),
                responsible_person=c.get("responsible_person"),
                acked_at=None,
                parameter_status=build_parameter_status(c),
                days_since_admission=(c.get("_derived") or {}).get("days_since_admission", 0),
                langlieger=build_langlieger_status(c),
            ))

    return all_cases



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

        # Per-category severity
        comp_alerts = [a for a in visible_alerts if a.category == "completeness"]
        med_alerts = [a for a in visible_alerts if a.category == "medical"]
        comp_sev, _, comp_cc, comp_wc = summarize_severity(comp_alerts)
        med_sev, _, med_cc, med_wc = summarize_severity(med_alerts)

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
                completeness_severity=comp_sev,
                completeness_critical=comp_cc,
                completeness_warn=comp_wc,
                medical_severity=med_sev,
                medical_critical=med_cc,
                medical_warn=med_wc,
                case_status=c.get("case_status"),
                responsible_person=c.get("responsible_person"),
                acked_at=case_level_acked_at.get(c["case_id"]),
                parameter_status=build_parameter_status(c),
                days_since_admission=(c.get("_derived") or {}).get("days_since_admission", 0),
                langlieger=build_langlieger_status(c),
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

    _validate_case_id(case_id)
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

    # Per-category severity
    comp_alerts = [a for a in visible_alerts if a.category == "completeness"]
    med_alerts = [a for a in visible_alerts if a.category == "medical"]
    comp_sev, _, comp_cc, comp_wc = summarize_severity(comp_alerts)
    med_sev, _, med_cc, med_wc = summarize_severity(med_alerts)

    # ─── Parameter Groups mit ACK/Alert-Enrichment ───
    param_groups = build_parameter_groups(c)
    # Alert-Lookup: rule_id -> Alert (für explanation + condition_hash)
    alert_by_rule = {a.rule_id: a for a in raw_alerts}
    for group in param_groups:
        for item in group["items"]:
            rid = item.get("rule_id")
            if not rid:
                continue
            alert = alert_by_rule.get(rid)
            if alert:
                item["explanation"] = alert.explanation
                item["condition_hash"] = alert.condition_hash
            # ACK/SHIFT Status aus rule_states injizieren
            ack_info = rule_states.get(rid)
            if ack_info:
                item["ack"] = ack_info

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
        completeness_severity=comp_sev,
        completeness_critical=comp_cc,
        completeness_warn=comp_wc,
        medical_severity=med_sev,
        medical_critical=med_cc,
        medical_warn=med_wc,
        case_status=c.get("case_status"),
        responsible_person=c.get("responsible_person"),
        acked_at=acked_at,
        parameter_status=build_parameter_status(c),
        days_since_admission=(c.get("_derived") or {}).get("days_since_admission", 0),
        langlieger=build_langlieger_status(c),
        honos=c.get("honos_entry_total"),
        bscl=c.get("bscl_total_entry"),
        bfs_complete=not (c.get("_derived") or {}).get("bfs_incomplete", False),
        alerts=raw_alerts,  # ALLE Alerts (nicht nur visible) — Frontend entscheidet Anzeige
        rule_states=rule_states,
        parameter_groups=param_groups,
        fu_status=build_fu_status(c),
    )


@router.post("/api/ack")
def ack(
    req: AckRequest,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("ack:write")),
):

    if req.ack_scope not in ("case", "rule"):
        raise HTTPException(status_code=400, detail="ack_scope must be 'case' or 'rule'")

    _validate_case_id(req.case_id)
    raw = get_single_case(req.case_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")

    c = enrich_case(raw)
    if c["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")

    # ── ACK-Rollenprüfung: Case-Scope nur für Shift-Leads+ ──────────
    if req.ack_scope == "case":
        allowed_case_ack = {"system_admin", "admin", "manager", "shift_lead"}
        if not ctx.roles.intersection(allowed_case_ack):
            raise HTTPException(
                status_code=403,
                detail="Fall-Quittierung ist nur für Schichtleitung und höher erlaubt. Bitte einzelne Meldungen quittieren.",
            )

    # ── ACK-Rollenprüfung: Regel-spezifische Rollenbeschränkung ─────
    if req.ack_scope == "rule" and req.scope_id != "*":
        from app.rule_engine import load_rule_definitions
        rule_defs = load_rule_definitions()
        rule_def = next((r for r in rule_defs if r.rule_id == req.scope_id), None)
        if rule_def:
            # ack_roles_json: JSON-Array z.B. ["clinician", "system_admin"]
            ack_roles_raw = getattr(rule_def, "ack_roles_json", None)
            if ack_roles_raw:
                import json as _json
                try:
                    ack_roles = set(_json.loads(ack_roles_raw))
                except Exception:
                    ack_roles = set()
                if ack_roles and not ctx.roles.intersection(ack_roles):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Keine Berechtigung, Meldung '{rule_def.message}' zu quittieren. Erlaubt: {', '.join(sorted(ack_roles))}",
                    )
            # restrict_to_responsible: nur fallführende Person oder Leitung
            restrict = getattr(rule_def, "restrict_to_responsible", False)
            if restrict:
                responsible = c.get("responsible_person") or ""
                is_responsible = responsible and responsible == ctx.user_id
                is_lead = bool(ctx.roles.intersection({"system_admin", "admin", "manager", "shift_lead"}))
                if not is_responsible and not is_lead:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Nur fallführende Person ({responsible}) oder Leitung darf diese Meldung quittieren.",
                    )

    # --- Eingabevalidierung für SHIFT
    if (req.action or "ACK") == "SHIFT":
        # Validate shift code against configured reasons
        valid_codes = get_valid_shift_codes()
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

    # Audit: Jede Quittierung/Schiebung wird protokolliert
    action_type = req.action or "ACK"
    with SessionLocal() as audit_db:
        log_security_event(
            audit_db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action=f"CASE_{action_type}",
            target_type="case",
            target_id=req.case_id,
            success=True,
            message=f"{action_type} für {req.ack_scope}/{req.scope_id}",
            details={
                "ack_scope": req.ack_scope,
                "scope_id": req.scope_id,
                "condition_hash": condition_hash,
                "shift_code": req.shift_code,
                "business_date": business_date,
                "version": current_version,
            },
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
    request: Request,
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

    # Audit: Reset ist sicherheitsrelevant (invalidiert alle Quittierungen)
    with SessionLocal() as audit_db:
        log_security_event(
            audit_db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="RESET_TODAY",
            target_type="station",
            target_id=ctx.station_id,
            success=True,
            message=f"Tages-Reset: Version {old_v} → {old_v + 1}",
            details={"business_date": bdate, "old_version": old_v, "new_version": old_v + 1},
        )

    return {
        "station_id": ctx.station_id,
        "business_date": bdate,
        "version": get_day_version(station_id=ctx.station_id),
    }


@router.get("/api/cases/{case_id}/lab-history")
def case_lab_history(
    case_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Clozapin-Laborverlauf: Neutrophile, Spiegel, Troponin, Leber, Metabolik."""
    _validate_case_id(case_id)
    raw = get_single_case(case_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if raw["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case_id, "lab_history": get_lab_history(case_id)}


@router.get("/api/cases/{case_id}/ekg-history")
def case_ekg_history(
    case_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """EKG-Verlauf: QTc, Herzfrequenz, Rhythmus, Befunde."""
    _validate_case_id(case_id)
    raw = get_single_case(case_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if raw["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case_id, "ekg_history": get_ekg_history(case_id)}


@router.get("/api/cases/{case_id}/efm-events")
def case_efm_events(
    case_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Freiheitsbeschraenkende Massnahmen fuer einen Fall."""
    _validate_case_id(case_id)
    raw = get_single_case(case_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if raw["station_id"] != ctx.station_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case_id, "efm_events": get_efm_events(case_id)}


@router.get("/api/shift_reasons")
def list_shift_reasons(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
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
