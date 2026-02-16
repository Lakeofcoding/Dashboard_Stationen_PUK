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


# ---------------------------------------------------------------------------
# Dummy-Daten (Demo-Betrieb)
# ---------------------------------------------------------------------------

def make_dummy_cases() -> list[dict]:
    """Erstellt Demo-Faelle mit relativen Daten (immer aktuell)."""
    _today = date.today()
    return [
        {
            "case_id": "4645342", "patient_id": "4534234", "clinic": "EPP",
            "station_id": "A1", "center": "ZAPE",
            "admission_date": _today - timedelta(days=10), "discharge_date": None,
            "honos_entry_total": None, "honos_entry_date": None,
            "honos_discharge_total": None, "honos_discharge_date": None,
            "honos_discharge_suicidality": None,
            "bscl_total_entry": None, "bscl_entry_date": None,
            "bscl_total_discharge": None, "bscl_discharge_date": None,
            "bscl_discharge_suicidality": None,
            "bfs_1": 11, "bfs_2": None, "bfs_3": None, "isolations": [],
        },
        {
            "case_id": "4645343", "patient_id": "4534235", "clinic": "EPP",
            "station_id": "B0", "center": "ZDAP",
            "admission_date": _today - timedelta(days=12),
            "discharge_date": _today - timedelta(days=2),
            "honos_entry_total": 12, "honos_entry_date": _today - timedelta(days=11),
            "honos_discharge_total": 20, "honos_discharge_date": _today - timedelta(days=2),
            "honos_discharge_suicidality": 1,
            "bscl_total_entry": 40, "bscl_entry_date": _today - timedelta(days=11),
            "bscl_total_discharge": 50, "bscl_discharge_date": _today - timedelta(days=2),
            "bscl_discharge_suicidality": 2,
            "bfs_1": 10, "bfs_2": 12, "bfs_3": 9, "isolations": [],
        },
        {
            "case_id": "4645344", "patient_id": "4534236", "clinic": "EPP",
            "station_id": "B2", "center": "ZDAP",
            "admission_date": _today - timedelta(days=20),
            "discharge_date": _today - timedelta(days=5),
            "honos_entry_total": 18, "honos_entry_date": _today - timedelta(days=19),
            "honos_discharge_total": None, "honos_discharge_date": None,
            "honos_discharge_suicidality": None,
            "bscl_total_entry": 55, "bscl_entry_date": _today - timedelta(days=19),
            "bscl_total_discharge": None, "bscl_discharge_date": None,
            "bscl_discharge_suicidality": None,
            "bfs_1": None, "bfs_2": None, "bfs_3": None, "isolations": [],
        },
        {
            "case_id": "4645345", "patient_id": "4534237", "clinic": "EPP",
            "station_id": "A1", "center": "ZAPE",
            "admission_date": _today - timedelta(days=14),
            "discharge_date": _today - timedelta(days=1),
            "honos_entry_total": 16, "honos_entry_date": _today - timedelta(days=13),
            "honos_discharge_total": 15, "honos_discharge_date": _today - timedelta(days=1),
            "honos_discharge_suicidality": 3,
            "bscl_total_entry": 48, "bscl_entry_date": _today - timedelta(days=13),
            "bscl_total_discharge": 47, "bscl_discharge_date": _today - timedelta(days=1),
            "bscl_discharge_suicidality": 2,
            "bfs_1": 7, "bfs_2": 8, "bfs_3": 9,
            "isolations": [
                {"start": (_today - timedelta(days=3)).isoformat() + "T08:00:00Z", "stop": None}
            ],
        },
        {
            "case_id": "4645346", "patient_id": "4534238", "clinic": "EPP",
            "station_id": "B0", "center": "ZDAP",
            "admission_date": _today - timedelta(days=8), "discharge_date": None,
            "honos_entry_total": 22, "honos_entry_date": _today - timedelta(days=7),
            "honos_discharge_total": None, "honos_discharge_date": None,
            "honos_discharge_suicidality": None,
            "bscl_total_entry": 60, "bscl_entry_date": _today - timedelta(days=7),
            "bscl_total_discharge": None, "bscl_discharge_date": None,
            "bscl_discharge_suicidality": 3,
            "bfs_1": 1, "bfs_2": 2, "bfs_3": 3,
            "isolations": [
                {"start": (_today - timedelta(days=4)).isoformat() + "T08:00:00Z", "stop": None}
            ],
        },
        {
            "case_id": "4645347", "patient_id": "4534239", "clinic": "EPP",
            "station_id": "B2", "center": "ZDAP",
            "admission_date": _today - timedelta(days=15), "discharge_date": None,
            "honos_entry_total": 10, "honos_entry_date": _today - timedelta(days=14),
            "honos_discharge_total": None, "honos_discharge_date": None,
            "honos_discharge_suicidality": None,
            "bscl_total_entry": 35, "bscl_entry_date": _today - timedelta(days=14),
            "bscl_total_discharge": None, "bscl_discharge_date": None,
            "bscl_discharge_suicidality": None,
            "bfs_1": 4, "bfs_2": 5, "bfs_3": 6,
            "isolations": [
                {"start": (_today - timedelta(days=10)).isoformat() + "T10:00:00Z",
                 "stop": (_today - timedelta(days=10)).isoformat() + "T14:00:00Z"},
                {"start": (_today - timedelta(days=8)).isoformat() + "T12:00:00Z",
                 "stop": (_today - timedelta(days=8)).isoformat() + "T15:00:00Z"},
            ],
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
                admission_date=c["admission_date"].isoformat() if isinstance(c["admission_date"], date) else str(c["admission_date"]),
                discharge_date=c["discharge_date"].isoformat() if isinstance(c.get("discharge_date"), date) else None,
                honos_entry_total=c.get("honos_entry_total"),
                honos_entry_date=c.get("honos_entry_date", "").isoformat() if isinstance(c.get("honos_entry_date"), date) else None,
                honos_discharge_total=c.get("honos_discharge_total"),
                honos_discharge_date=c.get("honos_discharge_date", "").isoformat() if isinstance(c.get("honos_discharge_date"), date) else None,
                honos_discharge_suicidality=c.get("honos_discharge_suicidality"),
                bscl_total_entry=c.get("bscl_total_entry"),
                bscl_entry_date=c.get("bscl_entry_date", "").isoformat() if isinstance(c.get("bscl_entry_date"), date) else None,
                bscl_total_discharge=c.get("bscl_total_discharge"),
                bscl_discharge_date=c.get("bscl_discharge_date", "").isoformat() if isinstance(c.get("bscl_discharge_date"), date) else None,
                bscl_discharge_suicidality=c.get("bscl_discharge_suicidality"),
                bfs_1=str(c.get("bfs_1")) if c.get("bfs_1") is not None else None,
                bfs_2=str(c.get("bfs_2")) if c.get("bfs_2") is not None else None,
                bfs_3=str(c.get("bfs_3")) if c.get("bfs_3") is not None else None,
                isolations_json=json.dumps(c.get("isolations", [])) if c.get("isolations") else None,
                source="demo",
            )
            db.merge(case)
        db.commit()
        print(f"{len(DUMMY_CASES)} Demo-Faelle in DB importiert")
