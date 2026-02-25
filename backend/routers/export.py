"""
Router: /api/export – Tägliche und wöchentliche Exportlisten.

Gibt Fallnummern-Listen als JSON (für Frontend) oder CSV-Download zurück,
gruppiert nach den im Anforderungsdokument definierten Kategorien:

Täglich / Klinisch:
  - EKG nicht befundet (24h)
  - Clozapin: Neutrophile <2 G/l (48h)
  - Clozapin <19 Wo: Grosses BB fehlt (7d)
  - Clozapin <5 Wo: Troponin fehlt (7d)

Täglich / Kosten & Qualität:
  - Eintritt <72h, kein HoNOS
  - Eintritt <72h, nicht-freiwillig, kein Behandlungsplan
  - Austritt <72h, kein Austritts-HoNOS
  - Austritt <72h, BFS nicht abgeschlossen
  - Austritt <72h, SDEP nicht abgeschlossen

Wöchentlich / Klinisch:
  - Eintritt >7d, kein EKG
  - NotfallBEM >3d
  - Notfallmedikation >3d
  - Eintritt >7d, Allergien nicht erfasst
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth import AuthContext, get_auth_context
from app.rbac import require_permission
from app.case_logic import enrich_case
from app.day_state import today_local

router = APIRouter(tags=["export"])


# ---- Datenquellen ----

def _load_all_enriched(station_ids: list[str] | None = None) -> list[dict]:
    """Alle Fälle laden und anreichern. Optional nach Stationen filtern."""
    from app.case_logic import _load_raw_cases_from_db

    result = []
    seen = set()
    if station_ids:
        for sid in station_ids:
            for c in _load_raw_cases_from_db(sid):
                if c["case_id"] not in seen:
                    seen.add(c["case_id"])
                    result.append(enrich_case(c))
    else:
        from app.config import STATION_CENTER
        for sid in STATION_CENTER:
            for c in _load_raw_cases_from_db(sid):
                if c["case_id"] not in seen:
                    seen.add(c["case_id"])
                    result.append(enrich_case(c))

    # Wenn DB leer: leere Liste (kein stiller Fallback auf DUMMY_CASES)
    if not result:
        print("[export] WARNUNG: Keine Fälle in DB gefunden für Export")

    return result


# ---- Filterlogik ----

REPORT_DEFINITIONS = {
    # --- Täglich / Klinisch ---
    "ekg_not_reported_24h": {
        "label": "EKG nicht befundet (24h)",
        "frequency": "daily",
        "category": "medical",
        "metric": "ekg_not_reported_24h",
    },
    "clozapin_neutrophils_low": {
        "label": "Clozapin: Neutrophile <2 G/l (48h)",
        "frequency": "daily",
        "category": "medical",
        "metric": "clozapin_neutrophils_low",
    },
    "clozapin_cbc_missing_early": {
        "label": "Clozapin <19 Wo: Grosses BB fehlt (7d)",
        "frequency": "daily",
        "category": "medical",
        "metric": "clozapin_cbc_missing_early",
    },
    "clozapin_troponin_missing_early": {
        "label": "Clozapin <5 Wo: Troponin fehlt (7d)",
        "frequency": "daily",
        "category": "medical",
        "metric": "clozapin_troponin_missing_early",
    },
    # --- Täglich / Kosten & Qualität ---
    "honos_entry_missing": {
        "label": "Eintritt, kein HoNOS",
        "frequency": "daily",
        "category": "completeness",
        "filter": lambda c: c.get("honos_entry_total") is None and c.get("discharge_date") is None,
    },
    "treatment_plan_missing": {
        "label": "Nicht-freiwillig, kein Behandlungsplan",
        "frequency": "daily",
        "category": "completeness",
        "metric": "treatment_plan_missing_involuntary_72h",
    },
    "honos_discharge_missing": {
        "label": "Austritt, kein Austritts-HoNOS",
        "frequency": "daily",
        "category": "completeness",
        "filter": lambda c: (
            c.get("discharge_date") is not None
            and c.get("honos_discharge_total") is None
        ),
    },
    "bfs_incomplete": {
        "label": "Austritt, BFS nicht abgeschlossen",
        "frequency": "daily",
        "category": "completeness",
        "metric": "bfs_incomplete",
    },
    "sdep_incomplete": {
        "label": "Austritt, SDEP nicht abgeschlossen",
        "frequency": "daily",
        "category": "completeness",
        "metric": "sdep_incomplete_at_discharge",
    },
    # --- Wöchentlich / Klinisch ---
    "ekg_entry_missing_7d": {
        "label": "Eintritt >7d, kein EKG",
        "frequency": "weekly",
        "category": "medical",
        "metric": "ekg_entry_missing_7d",
    },
    "emergency_bem_over_3d": {
        "label": "NotfallBEM >3 Tage",
        "frequency": "weekly",
        "category": "medical",
        "metric": "emergency_bem_over_3d",
    },
    "emergency_med_over_3d": {
        "label": "Notfallmedikation >3 Tage",
        "frequency": "weekly",
        "category": "medical",
        "metric": "emergency_med_over_3d",
    },
    "allergies_missing_7d": {
        "label": "Eintritt >7d, Allergien nicht erfasst",
        "frequency": "weekly",
        "category": "medical",
        "metric": "allergies_missing_7d",
    },
}


def _filter_cases(cases: list[dict], report_id: str) -> list[dict]:
    defn = REPORT_DEFINITIONS.get(report_id)
    if not defn:
        return []
    if "filter" in defn:
        return [c for c in cases if defn["filter"](c)]
    metric = defn.get("metric")
    if metric:
        return [c for c in cases if (c.get("_derived") or {}).get(metric)]
    return []


# ---- Endpoints ----

@router.get("/api/export/reports")
def list_reports(
    frequency: Literal["daily", "weekly", "all"] = "all",
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Verfügbare Report-Definitionen auflisten."""
    reports = []
    for rid, defn in REPORT_DEFINITIONS.items():
        if frequency != "all" and defn["frequency"] != frequency:
            continue
        reports.append({
            "id": rid,
            "label": defn["label"],
            "frequency": defn["frequency"],
            "category": defn["category"],
        })
    return reports


@router.get("/api/export/data")
def export_data(
    report_id: str = Query(..., description="Report ID aus /api/export/reports"),
    station_id: str | None = Query(None, description="Station filtern (optional)"),
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Fallnummern-Liste für einen Report als JSON."""
    stations = [station_id] if station_id else None
    all_cases = _load_all_enriched(stations)
    hits = _filter_cases(all_cases, report_id)

    defn = REPORT_DEFINITIONS.get(report_id, {})
    return {
        "report_id": report_id,
        "label": defn.get("label", report_id),
        "frequency": defn.get("frequency"),
        "category": defn.get("category"),
        "date": today_local().isoformat(),
        "total": len(hits),
        "cases": [
            {
                "case_id": c["case_id"],
                "station_id": c["station_id"],
                "patient_id": c.get("patient_id", ""),
                "admission_date": str(c.get("admission_date", "")),
                "discharge_date": str(c.get("discharge_date", "")) if c.get("discharge_date") else None,
            }
            for c in hits
        ],
    }


@router.get("/api/export/csv")
def export_csv(
    report_id: str = Query(..., description="Report ID"),
    station_id: str | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Fallnummern-Liste als CSV-Download."""
    stations = [station_id] if station_id else None
    all_cases = _load_all_enriched(stations)
    hits = _filter_cases(all_cases, report_id)
    defn = REPORT_DEFINITIONS.get(report_id, {})

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Report", defn.get("label", report_id)])
    writer.writerow(["Datum", today_local().isoformat()])
    writer.writerow(["Anzahl", str(len(hits))])
    writer.writerow([])
    writer.writerow(["Fallnummer", "Station", "PatientenID", "Eintritt", "Austritt"])
    for c in hits:
        writer.writerow([
            c["case_id"],
            c["station_id"],
            c.get("patient_id", ""),
            str(c.get("admission_date", "")),
            str(c.get("discharge_date", "")) if c.get("discharge_date") else "",
        ])

    buf.seek(0)
    filename = f"{report_id}_{today_local().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/export/summary")
def export_summary(
    frequency: Literal["daily", "weekly"] = "daily",
    station_id: str | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Gesamtübersicht: Alle Reports einer Frequenz mit Fallzahlen."""
    stations = [station_id] if station_id else None
    all_cases = _load_all_enriched(stations)

    results = []
    for rid, defn in REPORT_DEFINITIONS.items():
        if defn["frequency"] != frequency:
            continue
        hits = _filter_cases(all_cases, rid)
        results.append({
            "report_id": rid,
            "label": defn["label"],
            "category": defn["category"],
            "count": len(hits),
            "case_ids": [c["case_id"] for c in hits],
        })

    return {
        "frequency": frequency,
        "date": today_local().isoformat(),
        "station_id": station_id,
        "reports": results,
    }
