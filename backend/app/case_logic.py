"""
Case-Logik: Laden, Anreicherung, Dummy-Daten.
Zentrale Business-Logic fuer Fall-Verarbeitung.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from app.config import STATION_CENTER, CLINIC_DEFAULT
from app.db import SessionLocal
from app.models import Case, ShiftReason
from app.day_state import today_local, _parse_iso_dt, get_day_version
from app.rule_engine import evaluate_alerts
from app.schemas import ParameterStatus
from app.excel_loader import get_demo_cases


def build_parameter_status(c: dict) -> list[dict]:
    """Baut die kompakte Parameterleiste fuer einen angereicherten Fall."""
    derived = c.get("_derived", {})
    discharge = c.get("discharge_date")
    is_active = discharge is None
    params = []

    # --- Completeness ---
    honos_e = c.get("honos_entry_total")
    if honos_e is not None:
        params.append({"id": "honos_entry", "label": "HoNOS ET", "group": "completeness", "status": "ok", "detail": f"Score: {honos_e}"})
    elif derived.get("honos_entry_missing_over_3d"):
        params.append({"id": "honos_entry", "label": "HoNOS ET", "group": "completeness", "status": "critical", "detail": "Fehlt >3d"})
    else:
        params.append({"id": "honos_entry", "label": "HoNOS ET", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    if discharge is not None:
        honos_d = c.get("honos_discharge_total")
        if honos_d is not None:
            params.append({"id": "honos_discharge", "label": "HoNOS AT", "group": "completeness", "status": "ok", "detail": f"Score: {honos_d}"})
        elif derived.get("honos_discharge_missing_over_3d_after_discharge"):
            params.append({"id": "honos_discharge", "label": "HoNOS AT", "group": "completeness", "status": "critical", "detail": "Fehlt >3d nach AT"})
        else:
            params.append({"id": "honos_discharge", "label": "HoNOS AT", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    bscl_e = c.get("bscl_total_entry")
    if bscl_e is not None:
        params.append({"id": "bscl_entry", "label": "BSCL ET", "group": "completeness", "status": "ok", "detail": f"Score: {bscl_e}"})
    elif derived.get("bscl_entry_missing_over_3d"):
        params.append({"id": "bscl_entry", "label": "BSCL ET", "group": "completeness", "status": "critical", "detail": "Fehlt >3d"})
    elif is_active:
        params.append({"id": "bscl_entry", "label": "BSCL ET", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    params.append({"id": "bfs", "label": "BFS", "group": "completeness",
                    "status": "ok" if not derived.get("bfs_incomplete") else "warn",
                    "detail": "Vollstaendig" if not derived.get("bfs_incomplete") else "Unvollstaendig"})

    if discharge is not None:
        sdep = c.get("sdep_complete")
        if sdep:
            params.append({"id": "sdep", "label": "SDEP", "group": "completeness", "status": "ok", "detail": "Abgeschlossen"})
        elif derived.get("sdep_incomplete_at_discharge"):
            params.append({"id": "sdep", "label": "SDEP", "group": "completeness", "status": "critical", "detail": "Nicht abgeschlossen"})
        elif not sdep:
            params.append({"id": "sdep", "label": "SDEP", "group": "completeness", "status": "warn", "detail": "Offen"})

    if not c.get("is_voluntary", True):
        tp = c.get("treatment_plan_date")
        if tp:
            params.append({"id": "treatment_plan", "label": "BehPlan", "group": "completeness", "status": "ok", "detail": "Erstellt"})
        elif derived.get("treatment_plan_missing_involuntary_72h"):
            params.append({"id": "treatment_plan", "label": "BehPlan", "group": "completeness", "status": "critical", "detail": "Fehlt (>72h)"})
        else:
            params.append({"id": "treatment_plan", "label": "BehPlan", "group": "completeness", "status": "warn", "detail": "Nicht erstellt"})

    # --- Medical ---
    if derived.get("ekg_not_reported_24h"):
        params.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "critical", "detail": "Nicht befundet (24h)"})
    elif derived.get("ekg_entry_missing_7d"):
        params.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "warn", "detail": "ET-EKG fehlt (>7d)"})
    elif c.get("ekg_entry_date") or c.get("ekg_last_date"):
        params.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "ok", "detail": "Dokumentiert"})
    elif is_active:
        params.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "na", "detail": None})

    if c.get("clozapin_active"):
        if derived.get("clozapin_neutrophils_low"):
            params.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "critical", "detail": "Neutrophile <2 G/l!"})
        elif derived.get("clozapin_troponin_missing_early"):
            params.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "warn", "detail": "Troponin fehlt (<5 Wo)"})
        elif derived.get("clozapin_cbc_missing_early"):
            params.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "warn", "detail": "BB fehlt (<19 Wo)"})
        else:
            params.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "ok", "detail": "Monitoring OK"})

    if derived.get("suicidality_discharge_high"):
        params.append({"id": "suicidality", "label": "Suizid.", "group": "medical", "status": "critical", "detail": "AT >= 3"})
    if derived.get("emergency_bem_over_3d"):
        params.append({"id": "notfall_bem", "label": "NotfBEM", "group": "medical", "status": "critical", "detail": ">3d aktiv"})
    if derived.get("emergency_med_over_3d"):
        params.append({"id": "notfall_med", "label": "NotfMed", "group": "medical", "status": "critical", "detail": ">3d aktiv"})

    if is_active:
        if c.get("allergies_recorded"):
            params.append({"id": "allergies", "label": "Allerg.", "group": "medical", "status": "ok", "detail": "Erfasst"})
        elif derived.get("allergies_missing_7d"):
            params.append({"id": "allergies", "label": "Allerg.", "group": "medical", "status": "warn", "detail": "Fehlt (>7d)"})

    if derived.get("isolation_open_over_48h"):
        params.append({"id": "isolation", "label": "Iso.", "group": "medical", "status": "critical", "detail": "Offen >48h"})
    elif derived.get("isolation_multiple"):
        params.append({"id": "isolation", "label": "Iso.", "group": "medical", "status": "warn", "detail": "Mehrfach"})

    return params


# ---------------------------------------------------------------------------
# Dummy-Daten (Demo-Betrieb)
# ---------------------------------------------------------------------------

def make_dummy_cases() -> list[dict]:
    """Laedt Demo-Faelle aus Excel (backend/data/demo_cases.xlsx).
    Fallback auf minimale Hardcoded-Daten wenn Excel nicht vorhanden.
    """
    cases = get_demo_cases()
    if cases:
        return cases

    # Minimaler Fallback wenn keine Excel vorhanden
    _today = date.today()
    return [
        {
            "case_id": "DEMO001", "patient_id": "P001", "clinic": "EPP",
            "station_id": "Station A1", "center": "ZAPE",
            "admission_date": _today - timedelta(days=10), "discharge_date": None,
            "honos_entry_total": None, "honos_entry_date": None,
            "honos_discharge_total": None, "honos_discharge_date": None,
            "honos_discharge_suicidality": None,
            "bscl_total_entry": None, "bscl_entry_date": None,
            "bscl_total_discharge": None, "bscl_discharge_date": None,
            "bscl_discharge_suicidality": None,
            "bfs_1": None, "bfs_2": None, "bfs_3": None, "isolations": [],
            "is_voluntary": True, "treatment_plan_date": None, "sdep_complete": None,
            "ekg_last_date": None, "ekg_last_reported": None, "ekg_entry_date": None,
            "clozapin_active": False, "clozapin_start_date": None,
            "neutrophils_last_date": None, "neutrophils_last_value": None,
            "troponin_last_date": None, "cbc_last_date": None,
            "emergency_bem_start_date": None, "emergency_med_start_date": None,
            "allergies_recorded": True,
        },
    ]


DUMMY_CASES = make_dummy_cases()


# ---------------------------------------------------------------------------
# Case enrichment (Ableitung von Metriken)
# ---------------------------------------------------------------------------

def enrich_case(c: dict) -> dict:
    """Reichert einen Roh-Fall mit abgeleiteten Metriken an."""
    station_id = c["station_id"]
    center = STATION_CENTER.get(station_id, "UNKNOWN")
    clinic = c.get("clinic") or CLINIC_DEFAULT
    discharge_date: date | None = c.get("discharge_date")
    today = today_local()

    bfs_incomplete = any(c.get(k) is None for k in ("bfs_1", "bfs_2", "bfs_3"))

    honos_entry_total = c.get("honos_entry_total")
    bscl_entry_total = c.get("bscl_total_entry")
    days_since_admission = (today - c["admission_date"]).days

    honos_entry_missing_over_3d = honos_entry_total is None and days_since_admission > 3
    bscl_entry_missing_over_3d = bscl_entry_total is None and days_since_admission > 3

    honos_discharge_total = c.get("honos_discharge_total")
    bscl_discharge_total = c.get("bscl_total_discharge")
    days_from_discharge: int | None = None
    if discharge_date is not None:
        days_from_discharge = (today - discharge_date).days

    def _due_missing(total_val) -> bool:
        if discharge_date is None or total_val is not None or days_from_discharge is None:
            return False
        return abs(days_from_discharge) <= 3

    honos_discharge_due_missing = _due_missing(honos_discharge_total)
    bscl_discharge_due_missing = _due_missing(bscl_discharge_total)
    honos_discharge_missing_over_3d_after_discharge = (
        discharge_date is not None and honos_discharge_total is None
        and days_from_discharge is not None and days_from_discharge > 3
    )
    bscl_discharge_missing_over_3d_after_discharge = (
        discharge_date is not None and bscl_discharge_total is None
        and days_from_discharge is not None and days_from_discharge > 3
    )

    honos_delta = None
    if honos_entry_total is not None and honos_discharge_total is not None:
        honos_delta = honos_discharge_total - honos_entry_total
    bscl_delta = None
    if bscl_entry_total is not None and bscl_discharge_total is not None:
        bscl_delta = bscl_discharge_total - bscl_entry_total

    suicidality_discharge_high = False
    if discharge_date is not None:
        h = c.get("honos_discharge_suicidality")
        b = c.get("bscl_discharge_suicidality")
        suicidality_discharge_high = (h is not None and h >= 3) or (b is not None and b >= 3)

    isolations = c.get("isolations") or []
    isolation_multiple = len(isolations) > 1
    now_utc = datetime.now(timezone.utc)
    isolation_open_over_48h = False
    for ep in isolations:
        start = ep.get("start")
        if not start or ep.get("stop") is not None:
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

    # --- Neue klinische Metriken (v2) ---

    # Behandlungsplan: nicht-freiwillig + > 72h ohne Plan
    is_voluntary = c.get("is_voluntary", True)
    treatment_plan_date = c.get("treatment_plan_date")
    treatment_plan_missing_involuntary_72h = (
        not is_voluntary
        and treatment_plan_date is None
        and days_since_admission > 3  # >72h
    )

    # SDEP bei Austritt
    sdep_complete = c.get("sdep_complete")
    sdep_incomplete_at_discharge = (
        discharge_date is not None
        and days_from_discharge is not None
        and days_from_discharge <= 3
        and not sdep_complete
    )

    # EKG nicht befundet in 24h
    ekg_last_date = c.get("ekg_last_date")
    ekg_last_reported = c.get("ekg_last_reported")
    ekg_not_reported_24h = False
    if ekg_last_date is not None and discharge_date is None:
        try:
            ekg_d = ekg_last_date if isinstance(ekg_last_date, date) else date.fromisoformat(str(ekg_last_date))
            if (today - ekg_d).days <= 1 and not ekg_last_reported:
                ekg_not_reported_24h = True
        except Exception:
            pass

    # Eintritts-EKG fehlt > 7 Tage
    ekg_entry_date = c.get("ekg_entry_date")
    ekg_entry_missing_7d = (
        discharge_date is None
        and days_since_admission > 7
        and ekg_entry_date is None
    )

    # Clozapin-Monitoring
    clozapin_active = c.get("clozapin_active", False)
    clozapin_start_date = c.get("clozapin_start_date")
    weeks_on_clozapin: float | None = None
    if clozapin_active and clozapin_start_date is not None:
        try:
            csd = clozapin_start_date if isinstance(clozapin_start_date, date) else date.fromisoformat(str(clozapin_start_date))
            weeks_on_clozapin = (today - csd).days / 7.0
        except Exception:
            pass

    # Neutrophile < 2 G/l (letzten 48h)
    clozapin_neutrophils_low = False
    if clozapin_active:
        neut_val = c.get("neutrophils_last_value")
        neut_date = c.get("neutrophils_last_date")
        if neut_val is not None and neut_date is not None:
            try:
                nd = neut_date if isinstance(neut_date, date) else date.fromisoformat(str(neut_date))
                if (today - nd).days <= 2 and float(neut_val) < 2.0:
                    clozapin_neutrophils_low = True
            except Exception:
                pass

    # Grosses Blutbild fehlt (< 19 Wochen Clozapin, > 7 Tage seit letztem)
    clozapin_cbc_missing_early = False
    if clozapin_active and weeks_on_clozapin is not None and weeks_on_clozapin < 19:
        cbc_last = c.get("cbc_last_date")
        if cbc_last is None:
            clozapin_cbc_missing_early = True
        else:
            try:
                cbd = cbc_last if isinstance(cbc_last, date) else date.fromisoformat(str(cbc_last))
                if (today - cbd).days > 7:
                    clozapin_cbc_missing_early = True
            except Exception:
                pass

    # Troponin fehlt (< 5 Wochen Clozapin, > 7 Tage seit letztem)
    clozapin_troponin_missing_early = False
    if clozapin_active and weeks_on_clozapin is not None and weeks_on_clozapin < 5:
        trop_last = c.get("troponin_last_date")
        if trop_last is None:
            clozapin_troponin_missing_early = True
        else:
            try:
                td = trop_last if isinstance(trop_last, date) else date.fromisoformat(str(trop_last))
                if (today - td).days > 7:
                    clozapin_troponin_missing_early = True
            except Exception:
                pass

    # Notfall-BEM > 3 Tage
    emergency_bem_start = c.get("emergency_bem_start_date")
    emergency_bem_over_3d = False
    if emergency_bem_start is not None and discharge_date is None:
        try:
            ebd = emergency_bem_start if isinstance(emergency_bem_start, date) else date.fromisoformat(str(emergency_bem_start))
            if (today - ebd).days > 3:
                emergency_bem_over_3d = True
        except Exception:
            pass

    # Notfallmedikation > 3 Tage
    emergency_med_start = c.get("emergency_med_start_date")
    emergency_med_over_3d = False
    if emergency_med_start is not None and discharge_date is None:
        try:
            emd = emergency_med_start if isinstance(emergency_med_start, date) else date.fromisoformat(str(emergency_med_start))
            if (today - emd).days > 3:
                emergency_med_over_3d = True
        except Exception:
            pass

    # Allergien nicht erfasst > 7 Tage
    allergies_recorded = c.get("allergies_recorded")
    allergies_missing_7d = (
        discharge_date is None
        and days_since_admission > 7
        and not allergies_recorded
    )

    out["_derived"] = {
        "honos_entry_missing_over_3d": honos_entry_missing_over_3d,
        "bscl_entry_missing_over_3d": bscl_entry_missing_over_3d,
        "honos_discharge_due_missing": honos_discharge_due_missing,
        "honos_discharge_missing_over_3d_after_discharge": honos_discharge_missing_over_3d_after_discharge,
        "bscl_discharge_due_missing": bscl_discharge_due_missing,
        "bscl_discharge_missing_over_3d_after_discharge": bscl_discharge_missing_over_3d_after_discharge,
        "honos_delta": honos_delta, "bscl_delta": bscl_delta,
        "suicidality_discharge_high": suicidality_discharge_high,
        "isolation_open_over_48h": isolation_open_over_48h,
        "isolation_multiple": isolation_multiple,
        "bfs_incomplete": bfs_incomplete,
        # Neue Metriken (v2)
        "treatment_plan_missing_involuntary_72h": treatment_plan_missing_involuntary_72h,
        "sdep_incomplete_at_discharge": sdep_incomplete_at_discharge,
        "ekg_not_reported_24h": ekg_not_reported_24h,
        "ekg_entry_missing_7d": ekg_entry_missing_7d,
        "clozapin_neutrophils_low": clozapin_neutrophils_low,
        "clozapin_cbc_missing_early": clozapin_cbc_missing_early,
        "clozapin_troponin_missing_early": clozapin_troponin_missing_early,
        "emergency_bem_over_3d": emergency_bem_over_3d,
        "emergency_med_over_3d": emergency_med_over_3d,
        "allergies_missing_7d": allergies_missing_7d,
    }
    return out


# ---------------------------------------------------------------------------
# Case loading (DB)
# ---------------------------------------------------------------------------

def _load_raw_cases_from_db(station_id: str) -> list[dict]:
    """Alle Faelle einer Station aus der DB (ohne Filterung)."""
    with SessionLocal() as db:
        cases = db.query(Case).filter(Case.station_id == station_id).all()
        result = []
        for c in cases:
            case_dict = {
                "case_id": c.case_id,
                "patient_id": c.patient_id or c.case_id,
                "clinic": c.clinic or "EPP",
                "station_id": c.station_id,
                "center": c.center or STATION_CENTER.get(c.station_id, "UNKNOWN"),
                "admission_date": date.fromisoformat(c.admission_date) if c.admission_date else today_local(),
                "discharge_date": date.fromisoformat(c.discharge_date) if c.discharge_date else None,
                "honos_entry_total": c.honos_entry_total,
                "honos_entry_date": date.fromisoformat(c.honos_entry_date) if c.honos_entry_date else None,
                "honos_discharge_total": c.honos_discharge_total,
                "honos_discharge_date": date.fromisoformat(c.honos_discharge_date) if c.honos_discharge_date else None,
                "honos_discharge_suicidality": c.honos_discharge_suicidality,
                "bscl_total_entry": c.bscl_total_entry,
                "bscl_entry_date": date.fromisoformat(c.bscl_entry_date) if c.bscl_entry_date else None,
                "bscl_total_discharge": c.bscl_total_discharge,
                "bscl_discharge_date": date.fromisoformat(c.bscl_discharge_date) if c.bscl_discharge_date else None,
                "bscl_discharge_suicidality": c.bscl_discharge_suicidality,
                "bfs_1": int(c.bfs_1) if c.bfs_1 and c.bfs_1.isdigit() else c.bfs_1,
                "bfs_2": int(c.bfs_2) if c.bfs_2 and c.bfs_2.isdigit() else c.bfs_2,
                "bfs_3": int(c.bfs_3) if c.bfs_3 and c.bfs_3.isdigit() else c.bfs_3,
                "isolations": json.loads(c.isolations_json) if c.isolations_json else [],
                # Neue Felder (v2)
                "is_voluntary": c.is_voluntary if c.is_voluntary is not None else True,
                "treatment_plan_date": date.fromisoformat(c.treatment_plan_date) if c.treatment_plan_date else None,
                "sdep_complete": c.sdep_complete,
                "ekg_last_date": date.fromisoformat(c.ekg_last_date) if c.ekg_last_date else None,
                "ekg_last_reported": c.ekg_last_reported,
                "ekg_entry_date": date.fromisoformat(c.ekg_entry_date) if c.ekg_entry_date else None,
                "clozapin_active": c.clozapin_active or False,
                "clozapin_start_date": date.fromisoformat(c.clozapin_start_date) if c.clozapin_start_date else None,
                "neutrophils_last_date": date.fromisoformat(c.neutrophils_last_date) if c.neutrophils_last_date else None,
                "neutrophils_last_value": c.neutrophils_last_value,
                "troponin_last_date": date.fromisoformat(c.troponin_last_date) if c.troponin_last_date else None,
                "cbc_last_date": date.fromisoformat(c.cbc_last_date) if c.cbc_last_date else None,
                "emergency_bem_start_date": date.fromisoformat(c.emergency_bem_start_date) if c.emergency_bem_start_date else None,
                "emergency_med_start_date": date.fromisoformat(c.emergency_med_start_date) if c.emergency_med_start_date else None,
                "allergies_recorded": c.allergies_recorded,
            }
            result.append(case_dict)
        return result


def _all_alerts_resolved(case_dict: dict, station_id: str, ack_store) -> bool:
    """Prueft ob alle Alerts eines Falls quittiert sind."""
    from app.rule_engine import evaluate_alerts as _eval
    case_id = case_dict["case_id"]
    enriched = enrich_case(case_dict)
    alerts = _eval(enriched)
    if not alerts:
        return True
    current_version = get_day_version(station_id=station_id)
    acks = ack_store.get_acks_for_cases([case_id], station_id)
    current_hashes = {a.rule_id: a.condition_hash for a in alerts}
    handled = set()
    for a in acks:
        if a.ack_scope == "rule":
            rid = a.scope_id
            if current_hashes.get(rid) and getattr(a, "condition_hash", None) == current_hashes[rid]:
                handled.add(rid)
    return all(a.rule_id in handled for a in alerts)


def load_cases_from_db(station_id: str, ack_store=None) -> list[dict]:
    """Faelle mit Auto-Expire-Filterung (3 Tage nach Austritt wenn alles quittiert)."""
    all_cases = _load_raw_cases_from_db(station_id)
    result = []
    for c in all_cases:
        if c["discharge_date"]:
            try:
                days_since = (today_local() - c["discharge_date"]).days
                if days_since > 3 and ack_store and _all_alerts_resolved(c, station_id, ack_store):
                    continue
            except Exception:
                pass
        result.append(c)
    return result


def get_station_cases(station_id: str, ack_store=None) -> list[dict]:
    """Angereicherte Faelle fuer eine Station."""
    db_cases = load_cases_from_db(station_id, ack_store)
    if db_cases:
        return [enrich_case(c) for c in db_cases]
    return [enrich_case(c) for c in DUMMY_CASES if c["station_id"] == station_id]


def get_single_case(case_id: str) -> dict | None:
    """Einzelnen Fall laden (ohne Auto-Expire, fuer Detail-View)."""
    with SessionLocal() as db:
        case_obj = db.get(Case, case_id)
        if case_obj:
            raw_cases = _load_raw_cases_from_db(case_obj.station_id)
            return next((c for c in raw_cases if c["case_id"] == case_id), None)
    return next((x for x in DUMMY_CASES if x["case_id"] == case_id), None)


def get_valid_shift_codes() -> set[str]:
    """Gueltige Schiebe-Codes aus DB."""
    with SessionLocal() as db:
        reasons = db.query(ShiftReason).filter(ShiftReason.is_active == True).all()  # noqa: E712
        codes = {r.code for r in reasons}
    return codes or {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_shift_reasons():
    """Standard-Schiebegruende anlegen."""
    defaults = [
        {"code": "a", "label": "Noch in Bearbeitung", "description": "Daten werden noch erfasst.", "sort_order": 1},
        {"code": "b", "label": "Warte auf Rueckmeldung", "description": "Information von anderer Stelle benoetigt.", "sort_order": 2},
        {"code": "c", "label": "Nicht relevant / Ausnahme", "description": "Klinisch begruendete Ausnahme.", "sort_order": 3},
    ]
    with SessionLocal() as db:
        if db.query(ShiftReason).count() == 0:
            for d in defaults:
                db.add(ShiftReason(**d, is_active=True))
            db.commit()
            print("Standard-Schiebegruende angelegt")


def _date_to_str(v) -> str | None:
    """Konvertiert date/datetime zu ISO-String fuer DB-Speicherung."""
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s if s and s.lower() not in ("nat", "nan", "none") else None


def seed_dummy_cases_to_db():
    """Demo-Faelle in DB seeden (werden bei jedem Start aufgefrischt)."""
    with SessionLocal() as db:
        db.query(Case).filter(Case.source == "demo").delete()
        db.commit()
        for c in DUMMY_CASES:
            case = Case(
                case_id=c["case_id"], station_id=c["station_id"],
                patient_id=c.get("patient_id"),
                clinic=c.get("clinic", "EPP"),
                center=STATION_CENTER.get(c["station_id"], "UNKNOWN"),
                admission_date=_date_to_str(c["admission_date"]) or date.today().isoformat(),
                discharge_date=_date_to_str(c.get("discharge_date")),
                honos_entry_total=c.get("honos_entry_total"),
                honos_entry_date=_date_to_str(c.get("honos_entry_date")),
                honos_discharge_total=c.get("honos_discharge_total"),
                honos_discharge_date=_date_to_str(c.get("honos_discharge_date")),
                honos_discharge_suicidality=c.get("honos_discharge_suicidality"),
                bscl_total_entry=c.get("bscl_total_entry"),
                bscl_entry_date=_date_to_str(c.get("bscl_entry_date")),
                bscl_total_discharge=c.get("bscl_total_discharge"),
                bscl_discharge_date=_date_to_str(c.get("bscl_discharge_date")),
                bscl_discharge_suicidality=c.get("bscl_discharge_suicidality"),
                bfs_1=str(c.get("bfs_1")) if c.get("bfs_1") is not None else None,
                bfs_2=str(c.get("bfs_2")) if c.get("bfs_2") is not None else None,
                bfs_3=str(c.get("bfs_3")) if c.get("bfs_3") is not None else None,
                isolations_json=json.dumps(c.get("isolations", [])) if c.get("isolations") else None,
                # Neue Felder (v2)
                is_voluntary=c.get("is_voluntary", True),
                treatment_plan_date=_date_to_str(c.get("treatment_plan_date")),
                sdep_complete=c.get("sdep_complete"),
                ekg_last_date=_date_to_str(c.get("ekg_last_date")),
                ekg_last_reported=c.get("ekg_last_reported"),
                ekg_entry_date=_date_to_str(c.get("ekg_entry_date")),
                clozapin_active=c.get("clozapin_active", False),
                clozapin_start_date=_date_to_str(c.get("clozapin_start_date")),
                neutrophils_last_date=_date_to_str(c.get("neutrophils_last_date")),
                neutrophils_last_value=str(c["neutrophils_last_value"]) if c.get("neutrophils_last_value") is not None else None,
                troponin_last_date=_date_to_str(c.get("troponin_last_date")),
                cbc_last_date=_date_to_str(c.get("cbc_last_date")),
                emergency_bem_start_date=_date_to_str(c.get("emergency_bem_start_date")),
                emergency_med_start_date=_date_to_str(c.get("emergency_med_start_date")),
                allergies_recorded=c.get("allergies_recorded"),
                source="demo",
            )
            db.merge(case)
        db.commit()
        print(f"{len(DUMMY_CASES)} Demo-Faelle in DB importiert")
