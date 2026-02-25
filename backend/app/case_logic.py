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
from app.schemas import ParameterStatus, ParameterGroup, LangliegerStatus, FuStatus
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

    if discharge is not None:
        bscl_d = c.get("bscl_total_discharge")
        if bscl_d is not None:
            params.append({"id": "bscl_discharge", "label": "BSCL AT", "group": "completeness", "status": "ok", "detail": f"Score: {bscl_d}"})
        elif derived.get("bscl_discharge_missing_over_3d_after_discharge"):
            params.append({"id": "bscl_discharge", "label": "BSCL AT", "group": "completeness", "status": "critical", "detail": "Fehlt >3d nach AT"})
        else:
            params.append({"id": "bscl_discharge", "label": "BSCL AT", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

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

    # Dokumentationsabschluss (nach Austritt)
    if discharge is not None:
        cs = c.get("case_status", "")
        if cs == "Dokumentation abgeschlossen":
            params.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "ok", "detail": "Abgeschlossen"})
        elif derived.get("doc_completion_overdue"):
            params.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "critical", "detail": "Überfällig (≥10d)"})
        elif derived.get("doc_completion_warn"):
            params.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "warn", "detail": "Offen"})
        elif cs == "Dokumentation offen":
            params.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "ok", "detail": "Im Zeitfenster"})

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


def _worst_severity(items: list[dict]) -> str:
    """Worst-child Severity: critical > warn > ok."""
    for sev in ("critical", "warn"):
        if any(i.get("status") == sev for i in items):
            return sev
    return "ok"


def _sev_to_api(s: str) -> str:
    """Konvertiert internen Status (ok/warn/critical) zu API Severity (OK/WARN/CRITICAL)."""
    return {"ok": "OK", "warn": "WARN", "critical": "CRITICAL"}.get(s, "OK")


def build_parameter_groups(c: dict) -> list[dict]:
    """Hierarchische Parametergruppen mit worst-child Severity-Kaskade."""
    derived = c.get("_derived", {})
    discharge = c.get("discharge_date")
    is_active = discharge is None
    groups = []

    # ─── SpiGes Personendaten ───
    spiges_person = []
    if derived.get("zivilstand_missing"):
        spiges_person.append({"id": "zivilstand", "label": "Zivilstand", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    elif derived.get("zivilstand_unknown"):
        spiges_person.append({"id": "zivilstand", "label": "Zivilstand", "group": "completeness", "status": "warn", "detail": "Unbekannt"})
    else:
        spiges_person.append({"id": "zivilstand", "label": "Zivilstand", "group": "completeness", "status": "ok", "detail": c.get("zivilstand")})

    if derived.get("aufenthaltsort_missing"):
        spiges_person.append({"id": "aufenthaltsort", "label": "Aufenthaltsort", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        spiges_person.append({"id": "aufenthaltsort", "label": "Aufenthaltsort", "group": "completeness", "status": "ok", "detail": "Erfasst"})

    if derived.get("beschaeftigung_missing"):
        spiges_person.append({"id": "beschaeftigung", "label": "Beschäftigung", "group": "completeness", "status": "warn", "detail": "Keine Angabe (mind. 1 nötig)"})
    else:
        spiges_person.append({"id": "beschaeftigung", "label": "Beschäftigung", "group": "completeness", "status": "ok", "detail": "Erfasst"})

    if derived.get("schulbildung_missing"):
        spiges_person.append({"id": "schulbildung", "label": "Schulbildung", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        spiges_person.append({"id": "schulbildung", "label": "Schulbildung", "group": "completeness", "status": "ok", "detail": "Erfasst"})

    groups.append({
        "key": "spiges_person",
        "label": "SpiGes Personendaten",
        "severity": _sev_to_api(_worst_severity(spiges_person)),
        "items": spiges_person,
    })

    # ─── SpiGes Eintrittsmerkmale ───
    spiges_eintritt = []
    if derived.get("einweisende_instanz_missing"):
        spiges_eintritt.append({"id": "einweisende_instanz", "label": "Einw. Instanz", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        spiges_eintritt.append({"id": "einweisende_instanz", "label": "Einw. Instanz", "group": "completeness", "status": "ok", "detail": "Erfasst"})

    if derived.get("behandlungsgrund_missing"):
        spiges_eintritt.append({"id": "behandlungsgrund", "label": "Behandlungsgrund", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        spiges_eintritt.append({"id": "behandlungsgrund", "label": "Behandlungsgrund", "group": "completeness", "status": "ok", "detail": "Erfasst"})

    groups.append({
        "key": "spiges_eintritt",
        "label": "SpiGes Eintritt",
        "severity": _sev_to_api(_worst_severity(spiges_eintritt)),
        "items": spiges_eintritt,
    })

    # ─── SpiGes Austrittsmerkmale (nur bei Austritt) ───
    if discharge is not None:
        spiges_austritt = []
        for fld, lbl in [("entscheid_austritt", "Entscheid Austritt"), ("aufenthalt_nach_austritt", "Aufenthalt nach AT"),
                         ("behandlung_nach_austritt", "Behandlung nach AT"), ("behandlungsbereich", "Behandlungsbereich")]:
            if derived.get(f"{fld}_missing"):
                spiges_austritt.append({"id": fld, "label": lbl, "group": "completeness", "status": "warn", "detail": "Fehlt"})
            else:
                spiges_austritt.append({"id": fld, "label": lbl, "group": "completeness", "status": "ok", "detail": "Erfasst"})
        groups.append({
            "key": "spiges_austritt",
            "label": "SpiGes Austritt",
            "severity": _sev_to_api(_worst_severity(spiges_austritt)),
            "items": spiges_austritt,
        })

    # ─── SpiGes Behandlung (MP 3.4) ───
    spiges_behandlung = []
    if derived.get("behandlung_typ_missing"):
        spiges_behandlung.append({"id": "behandlung_typ", "label": "Behandlungstyp", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        spiges_behandlung.append({"id": "behandlung_typ", "label": "Behandlungstyp", "group": "completeness", "status": "ok", "detail": c.get("behandlung_typ")})

    if derived.get("psychopharmaka_missing"):
        spiges_behandlung.append({"id": "psychopharmaka", "label": "Psychopharmaka", "group": "completeness", "status": "warn", "detail": "Keine Angabe (mind. 1 Feld nötig)"})
    else:
        # Zähle aktive Pharma
        pharma_labels = []
        for fk, fl in [("neuroleptika", "NL"), ("depotneuroleptika", "Depot-NL"), ("antidepressiva", "AD"),
                        ("tranquilizer", "Tranq."), ("hypnotika", "Hypn."), ("psychostimulanzien", "Stim."),
                        ("suchtaversionsmittel", "SuAv."), ("lithium", "Li"), ("antiepileptika", "AE"),
                        ("andere_psychopharmaka", "Andere")]:
            if c.get(fk) == 1:
                pharma_labels.append(fl)
        if c.get("keine_psychopharmaka") == 1:
            pharma_labels = ["Keine"]
        detail = ", ".join(pharma_labels) if pharma_labels else "Erfasst"
        spiges_behandlung.append({"id": "psychopharmaka", "label": "Psychopharmaka", "group": "completeness", "status": "ok", "detail": detail})

    groups.append({
        "key": "spiges_behandlung",
        "label": "SpiGes Behandlung",
        "severity": _sev_to_api(_worst_severity(spiges_behandlung)),
        "items": spiges_behandlung,
    })

    # ─── MB Minimaldaten ───
    mb_items = []
    if derived.get("eintrittsart_missing"):
        mb_items.append({"id": "eintrittsart", "label": "Eintrittsart", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        mb_items.append({"id": "eintrittsart", "label": "Eintrittsart", "group": "completeness", "status": "ok", "detail": c.get("eintrittsart")})
    if derived.get("klasse_missing"):
        mb_items.append({"id": "klasse", "label": "Klasse", "group": "completeness", "status": "warn", "detail": "Fehlt"})
    else:
        mb_items.append({"id": "klasse", "label": "Klasse", "group": "completeness", "status": "ok", "detail": c.get("klasse")})
    groups.append({
        "key": "mb_minimaldaten",
        "label": "Minimaldaten",
        "severity": _sev_to_api(_worst_severity(mb_items)),
        "items": mb_items,
    })

    # ─── FU (nur bei nicht-freiwilligen Patienten) ───
    if derived.get("is_fu"):
        fu_items = []
        if derived.get("fu_missing"):
            fu_items.append({"id": "fu_bei_eintritt", "label": "FU bei Eintritt", "group": "completeness", "status": "critical", "detail": "Nicht dokumentiert"})
        else:
            fu_items.append({"id": "fu_bei_eintritt", "label": "FU bei Eintritt", "group": "completeness", "status": "ok", "detail": "Dokumentiert"})

        if derived.get("fu_expired"):
            fu_items.append({"id": "fu_ablauf", "label": "FU Gültigkeit", "group": "medical", "status": "critical", "detail": "Abgelaufen!"})
        elif derived.get("fu_expiring_soon"):
            days_left = derived.get("fu_days_until_expiry", 0)
            fu_items.append({"id": "fu_ablauf", "label": "FU Gültigkeit", "group": "medical", "status": "warn", "detail": f"Läuft ab in {days_left}d"})
        elif c.get("fu_gueltig_bis"):
            fu_items.append({"id": "fu_ablauf", "label": "FU Gültigkeit", "group": "medical", "status": "ok", "detail": f"Gültig bis {c['fu_gueltig_bis']}"})

        groups.append({
            "key": "fu",
            "label": "FU",
            "severity": _sev_to_api(_worst_severity(fu_items)),
            "items": fu_items,
        })

    # ─── HoNOS ───
    honos_items = []
    honos_e = c.get("honos_entry_total")
    if honos_e is not None:
        honos_items.append({"id": "honos_entry", "label": "HoNOS ET", "group": "completeness", "status": "ok", "detail": f"Score: {honos_e}"})
    elif derived.get("honos_entry_missing_over_3d"):
        honos_items.append({"id": "honos_entry", "label": "HoNOS ET", "group": "completeness", "status": "critical", "detail": "Fehlt >3d"})
    else:
        honos_items.append({"id": "honos_entry", "label": "HoNOS ET", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    if discharge is not None:
        honos_d = c.get("honos_discharge_total")
        if honos_d is not None:
            honos_items.append({"id": "honos_discharge", "label": "HoNOS AT", "group": "completeness", "status": "ok", "detail": f"Score: {honos_d}"})
        elif derived.get("honos_discharge_missing_over_3d_after_discharge"):
            honos_items.append({"id": "honos_discharge", "label": "HoNOS AT", "group": "completeness", "status": "critical", "detail": "Fehlt >3d nach AT"})
        else:
            honos_items.append({"id": "honos_discharge", "label": "HoNOS AT", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    # HoNOS Delta (Verschlechterung)
    honos_delta = derived.get("honos_delta")
    if honos_delta is not None and honos_delta > 5:
        honos_items.append({"id": "honos_delta", "label": "HoNOS Δ", "group": "medical", "status": "warn", "detail": f"Verschlechterung: +{honos_delta}"})

    groups.append({
        "key": "honos", "label": "HoNOS",
        "severity": _sev_to_api(_worst_severity(honos_items)),
        "items": honos_items,
    })

    # ─── BSCL ───
    bscl_items = []
    bscl_e = c.get("bscl_total_entry")
    if bscl_e is not None:
        bscl_items.append({"id": "bscl_entry", "label": "BSCL ET", "group": "completeness", "status": "ok", "detail": f"Score: {bscl_e}"})
    elif derived.get("bscl_entry_missing_over_3d"):
        bscl_items.append({"id": "bscl_entry", "label": "BSCL ET", "group": "completeness", "status": "critical", "detail": "Fehlt >3d"})
    elif is_active:
        bscl_items.append({"id": "bscl_entry", "label": "BSCL ET", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    if discharge is not None:
        bscl_d = c.get("bscl_total_discharge")
        if bscl_d is not None:
            bscl_items.append({"id": "bscl_discharge", "label": "BSCL AT", "group": "completeness", "status": "ok", "detail": f"Score: {bscl_d}"})
        elif derived.get("bscl_discharge_missing_over_3d_after_discharge"):
            bscl_items.append({"id": "bscl_discharge", "label": "BSCL AT", "group": "completeness", "status": "critical", "detail": "Fehlt >3d nach AT"})
        else:
            bscl_items.append({"id": "bscl_discharge", "label": "BSCL AT", "group": "completeness", "status": "warn", "detail": "Nicht erfasst"})

    # BSCL Delta (Verschlechterung)
    bscl_delta = derived.get("bscl_delta")
    if bscl_delta is not None and bscl_delta > 5:
        bscl_items.append({"id": "bscl_delta", "label": "BSCL Δ", "group": "medical", "status": "warn", "detail": f"Verschlechterung: +{bscl_delta}"})

    if bscl_items:
        groups.append({
            "key": "bscl", "label": "BSCL",
            "severity": _sev_to_api(_worst_severity(bscl_items)),
            "items": bscl_items,
        })

    # ─── BFS ───
    bfs_items = []
    bfs_incomplete = derived.get("bfs_incomplete", False)
    bfs_items.append({"id": "bfs", "label": "BFS Paket", "group": "completeness",
                      "status": "warn" if bfs_incomplete else "ok",
                      "detail": "Unvollständig" if bfs_incomplete else "Vollständig"})
    groups.append({
        "key": "bfs", "label": "BFS",
        "severity": _sev_to_api(_worst_severity(bfs_items)),
        "items": bfs_items,
    })

    # ─── SDEP + Dok.Abschluss (nur bei Austritt) ───
    if discharge is not None:
        dok_items = []
        sdep = c.get("sdep_complete")
        if sdep:
            dok_items.append({"id": "sdep", "label": "SDEP", "group": "completeness", "status": "ok", "detail": "Abgeschlossen"})
        elif derived.get("sdep_incomplete_at_discharge"):
            dok_items.append({"id": "sdep", "label": "SDEP", "group": "completeness", "status": "critical", "detail": "Nicht abgeschlossen"})
        else:
            dok_items.append({"id": "sdep", "label": "SDEP", "group": "completeness", "status": "warn", "detail": "Offen"})

        cs = c.get("case_status", "")
        if cs == "Dokumentation abgeschlossen":
            dok_items.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "ok", "detail": "Abgeschlossen"})
        elif derived.get("doc_completion_overdue"):
            dok_items.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "critical", "detail": "Überfällig (≥10d)"})
        elif derived.get("doc_completion_warn"):
            dok_items.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "warn", "detail": "Offen"})
        elif cs == "Dokumentation offen":
            dok_items.append({"id": "doc_completion", "label": "Dok.Abschl.", "group": "completeness", "status": "ok", "detail": "Im Zeitfenster"})

        if dok_items:
            groups.append({
                "key": "dok_austritt", "label": "Austritts-Dokumentation",
                "severity": _sev_to_api(_worst_severity(dok_items)),
                "items": dok_items,
            })

    # ─── Behandlungsplan (nur bei nicht-freiwillig) ───
    if not c.get("is_voluntary", True):
        bp_items = []
        tp = c.get("treatment_plan_date")
        if tp:
            bp_items.append({"id": "treatment_plan", "label": "Behandlungsplan", "group": "completeness", "status": "ok", "detail": "Erstellt"})
        elif derived.get("treatment_plan_missing_involuntary_72h"):
            bp_items.append({"id": "treatment_plan", "label": "Behandlungsplan", "group": "completeness", "status": "critical", "detail": "Fehlt (>72h)"})
        else:
            bp_items.append({"id": "treatment_plan", "label": "Behandlungsplan", "group": "completeness", "status": "warn", "detail": "Nicht erstellt"})
        groups.append({
            "key": "behandlungsplan", "label": "Behandlungsplan",
            "severity": _sev_to_api(_worst_severity(bp_items)),
            "items": bp_items,
        })

    # ─── Langlieger ───
    if is_active and derived.get("days_since_admission", 0) >= 25:
        ll_items = []
        days = derived.get("days_since_admission", 0)
        if derived.get("langlieger_critical"):
            week = derived.get("langlieger_week", 4)
            ll_items.append({"id": "langlieger", "label": "Langlieger", "group": "medical", "status": "critical",
                             "detail": f"{days}d stationär (Woche {week})"})
        elif derived.get("langlieger_warn"):
            ll_items.append({"id": "langlieger", "label": "Langlieger", "group": "medical", "status": "warn",
                             "detail": f"{days}d stationär (≥25d)"})
        if ll_items:
            groups.append({
                "key": "langlieger", "label": "Langlieger",
                "severity": _sev_to_api(_worst_severity(ll_items)),
                "items": ll_items,
            })

    # ─── Klinisch / Medical ───
    med_items = []

    # EKG
    if derived.get("ekg_not_reported_24h"):
        med_items.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "critical", "detail": "Nicht befundet (24h)"})
    elif derived.get("ekg_entry_missing_7d"):
        med_items.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "warn", "detail": "ET-EKG fehlt (>7d)"})
    elif c.get("ekg_entry_date") or c.get("ekg_last_date"):
        med_items.append({"id": "ekg", "label": "EKG", "group": "medical", "status": "ok", "detail": "Dokumentiert"})

    # Clozapin
    if c.get("clozapin_active"):
        if derived.get("clozapin_neutrophils_low"):
            med_items.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "critical", "detail": "Neutrophile <2 G/l!"})
        elif derived.get("clozapin_troponin_missing_early"):
            med_items.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "warn", "detail": "Troponin fehlt (<5 Wo)"})
        elif derived.get("clozapin_cbc_missing_early"):
            med_items.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "warn", "detail": "BB fehlt (<19 Wo)"})
        else:
            med_items.append({"id": "clozapin", "label": "Clozapin", "group": "medical", "status": "ok", "detail": "Monitoring OK"})

    # Suizidalität
    if derived.get("suicidality_discharge_high"):
        med_items.append({"id": "suicidality", "label": "Suizid.", "group": "medical", "status": "critical", "detail": "AT >= 3"})

    # Notfall-BEM / NotfMed
    if derived.get("emergency_bem_over_3d"):
        med_items.append({"id": "notfall_bem", "label": "NotfBEM", "group": "medical", "status": "critical", "detail": ">3d aktiv"})
    if derived.get("emergency_med_over_3d"):
        med_items.append({"id": "notfall_med", "label": "NotfMed", "group": "medical", "status": "critical", "detail": ">3d aktiv"})

    # Allergien
    if is_active:
        if c.get("allergies_recorded"):
            med_items.append({"id": "allergies", "label": "Allergien", "group": "medical", "status": "ok", "detail": "Erfasst"})
        elif derived.get("allergies_missing_7d"):
            med_items.append({"id": "allergies", "label": "Allergien", "group": "medical", "status": "warn", "detail": "Fehlt (>7d)"})

    # Isolation
    if derived.get("isolation_open_over_48h"):
        med_items.append({"id": "isolation", "label": "Isolation", "group": "medical", "status": "critical", "detail": "Offen >48h"})
    elif derived.get("isolation_multiple"):
        med_items.append({"id": "isolation", "label": "Isolation", "group": "medical", "status": "warn", "detail": "Mehrfach"})

    if med_items:
        groups.append({
            "key": "klinisch", "label": "Klinisch",
            "severity": _sev_to_api(_worst_severity(med_items)),
            "items": med_items,
        })

    # ─── Post-Processing: rule_id Mapping ───
    # Verknüpft Parameter-Items mit ihren Regel-IDs für ACK/SHIFT-Workflow
    PARAM_RULE_MAP = {
        # SpiGes Personendaten
        ("zivilstand", "warn"): ["SPIGES_ZIVILSTAND_MISSING", "SPIGES_ZIVILSTAND_UNKNOWN"],
        ("aufenthaltsort", "warn"): ["SPIGES_AUFENTHALTSORT_MISSING"],
        ("beschaeftigung", "warn"): ["SPIGES_BESCHAEFTIGUNG_MISSING"],
        ("schulbildung", "warn"): ["SPIGES_SCHULBILDUNG_MISSING"],
        # SpiGes Eintritt
        ("einweisende_instanz", "warn"): ["SPIGES_EINWEISENDE_INSTANZ_MISSING"],
        ("behandlungsgrund", "warn"): ["SPIGES_BEHANDLUNGSGRUND_MISSING"],
        # SpiGes Austritt
        ("entscheid_austritt", "warn"): ["SPIGES_ENTSCHEID_AUSTRITT_MISSING"],
        ("aufenthalt_nach_austritt", "warn"): ["SPIGES_AUFENTHALT_NACH_AUSTRITT_MISSING"],
        ("behandlung_nach_austritt", "warn"): ["SPIGES_BEHANDLUNG_NACH_AUSTRITT_MISSING"],
        ("behandlungsbereich", "warn"): ["SPIGES_BEHANDLUNGSBEREICH_MISSING"],
        # SpiGes Behandlung
        ("behandlung_typ", "warn"): ["SPIGES_BEHANDLUNG_TYP_MISSING"],
        ("psychopharmaka", "warn"): ["SPIGES_PSYCHOPHARMAKA_MISSING"],
        # MB Minimaldaten
        ("eintrittsart", "warn"): ["MB_EINTRITTSART_MISSING"],
        ("klasse", "warn"): ["MB_KLASSE_MISSING"],
        # FU
        ("fu_bei_eintritt", "critical"): ["FU_MISSING"],
        ("fu_ablauf", "warn"): ["FU_EXPIRING_SOON"],
        ("fu_ablauf", "critical"): ["FU_EXPIRED"],
        # HoNOS
        ("honos_entry", "warn"): ["HONOS_ENTRY_MISSING_WARN"],
        ("honos_entry", "critical"): ["HONOS_ENTRY_MISSING_CRIT_3D"],
        ("honos_discharge", "warn"): ["HONOS_DISCHARGE_MISSING_WARN"],
        ("honos_discharge", "critical"): ["HONOS_DISCHARGE_MISSING_CRIT_3D"],
        # BSCL
        ("bscl_entry", "warn"): ["BSCL_ENTRY_MISSING_WARN"],
        ("bscl_entry", "critical"): ["BSCL_ENTRY_MISSING_CRIT_3D"],
        ("bscl_discharge", "warn"): ["BSCL_DISCHARGE_MISSING_WARN"],
        ("bscl_discharge", "critical"): ["BSCL_DISCHARGE_MISSING_CRIT_3D"],
        # BFS
        ("bfs", "warn"): ["BFS_INCOMPLETE"],
        # Dok Austritt
        ("sdep", "critical"): ["SDEP_INCOMPLETE_AT_DISCHARGE"],
        ("doc_completion", "warn"): ["DOC_COMPLETION_WARN"],
        ("doc_completion", "critical"): ["DOC_COMPLETION_OVERDUE"],
        # Behandlungsplan
        ("treatment_plan", "critical"): ["TREATMENT_PLAN_MISSING_72H"],
        ("treatment_plan", "warn"): ["TREATMENT_PLAN_MISSING_72H"],
        # Klinisch
        ("ekg", "critical"): ["EKG_NOT_REPORTED_24H"],
        ("ekg", "warn"): ["EKG_ENTRY_MISSING_7D"],
        ("clozapin", "critical"): ["CLOZAPIN_NEUTROPHILS_LOW"],
        ("clozapin", "warn"): ["CLOZAPIN_CBC_MISSING_EARLY", "CLOZAPIN_TROPONIN_MISSING_EARLY"],
        ("suicidality", "critical"): ["SUICIDALITY_HIGH_AT_DISCHARGE"],
        ("notfall_bem", "critical"): ["EMERGENCY_BEM_OVER_3D"],
        ("notfall_med", "critical"): ["EMERGENCY_MED_OVER_3D"],
        ("allergies", "warn"): ["ALLERGIES_MISSING_7D"],
        ("isolation", "critical"): ["ISOLATION_OPEN_GT_48H"],
        ("isolation", "warn"): ["ISOLATION_MULTIPLE"],
        # HoNOS/BSCL Delta
        ("honos_delta", "warn"): ["HONOS_DELTA_GT_5"],
        ("bscl_delta", "warn"): ["BSCL_DELTA_GT_5"],
        # Langlieger
        ("langlieger", "warn"): ["LANGLIEGER_WARN"],
        ("langlieger", "critical"): ["LANGLIEGER_CRITICAL"],
    }
    for group in groups:
        for item in group["items"]:
            if item["status"] in ("ok", "na"):
                continue
            candidates = PARAM_RULE_MAP.get((item["id"], item["status"]), [])
            if candidates:
                item["rule_id"] = candidates[0]  # primäre Regel

    return groups


def build_langlieger_status(c: dict) -> dict:
    """Top-Level Langlieger-Warnung mit Wochen-/Schwellenanzeige."""
    derived = c.get("_derived", {})
    days = derived.get("days_since_admission", 0)
    discharge = c.get("discharge_date")

    if discharge is not None or days < 25:
        return {"active": False, "severity": "OK", "days": days, "week": None, "message": None, "next_threshold": None}

    if derived.get("langlieger_critical"):
        week = derived.get("langlieger_week", 4)
        next_t = derived.get("langlieger_next_threshold", 42)
        return {
            "active": True, "severity": "CRITICAL", "days": days, "week": week,
            "message": f"Langlieger: {days} Tage (Woche {week})",
            "next_threshold": next_t,
        }

    return {
        "active": True, "severity": "WARN", "days": days, "week": None,
        "message": f"Langlieger-Warnung: {days} Tage (≥25d)",
        "next_threshold": 28,
    }


def build_fu_status(c: dict) -> dict:
    """FU-Zusammenfassung mit Ablauf-Countdown."""
    derived = c.get("_derived", {})
    is_fu = derived.get("is_fu", False)

    if not is_fu:
        return {"is_fu": False, "fu_typ": None, "fu_datum": None, "fu_gueltig_bis": None,
                "days_until_expiry": None, "severity": "OK", "message": None}

    fu_typ = c.get("fu_typ")
    fu_datum = c.get("fu_datum")
    fu_gueltig_bis = c.get("fu_gueltig_bis")
    days_until = derived.get("fu_days_until_expiry")

    if derived.get("fu_expired"):
        sev = "CRITICAL"
        msg = f"FU abgelaufen! ({abs(days_until)}d überfällig)" if days_until is not None else "FU abgelaufen!"
    elif derived.get("fu_expiring_soon"):
        sev = "WARN"
        msg = f"FU läuft ab in {days_until} Tagen" if days_until is not None else "FU läuft bald ab"
    elif derived.get("fu_missing"):
        sev = "CRITICAL"
        msg = "FU bei Eintritt nicht dokumentiert"
    else:
        sev = "OK"
        msg = f"FU gültig ({fu_typ or 'unbekannt'})"

    return {
        "is_fu": True, "fu_typ": fu_typ, "fu_datum": fu_datum, "fu_gueltig_bis": fu_gueltig_bis,
        "days_until_expiry": days_until, "severity": sev, "message": msg,
    }


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

    # Dokumentationsabschluss nach Austritt
    case_status = c.get("case_status")  # "Fall offen", "Dokumentation offen", "Dokumentation abgeschlossen"
    # Auto-Ableitung wenn nicht explizit gesetzt
    if not case_status:
        if discharge_date is None:
            case_status = "Fall offen"
        else:
            case_status = "Dokumentation abgeschlossen"  # Default bei fehlender Info
    doc_completion_warn = False   # Tag 1-9 nach Austritt: gelb
    doc_completion_overdue = False  # Ab Tag 10 nach Austritt: rot
    if discharge_date is not None and case_status == "Dokumentation offen" and days_from_discharge is not None:
        if days_from_discharge >= 10:
            doc_completion_overdue = True
        elif days_from_discharge >= 1:
            doc_completion_warn = True

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
        # Dokumentationsabschluss (v3)
        "doc_completion_warn": doc_completion_warn,
        "doc_completion_overdue": doc_completion_overdue,
        # Aufenthaltsdauer
        "days_since_admission": days_since_admission,
    }

    # ─── FU (Fürsorgerische Unterbringung) – v4 ───
    is_fu = not c.get("is_voluntary", True)
    fu_bei_eintritt = c.get("fu_bei_eintritt")
    fu_typ = c.get("fu_typ")
    fu_gueltig_bis_str = c.get("fu_gueltig_bis")
    fu_days_until_expiry: int | None = None
    fu_expired = False
    fu_expiring_soon = False  # ≤7 Tage bis Ablauf

    if is_fu and fu_gueltig_bis_str:
        try:
            fu_exp = fu_gueltig_bis_str if isinstance(fu_gueltig_bis_str, date) else date.fromisoformat(str(fu_gueltig_bis_str)[:10])
            fu_days_until_expiry = (fu_exp - today).days
            fu_expired = fu_days_until_expiry < 0
            fu_expiring_soon = 0 <= fu_days_until_expiry <= 7
        except Exception:
            pass

    fu_missing = is_fu and fu_bei_eintritt is None

    out["_derived"].update({
        # FU (v4)
        "is_fu": is_fu,
        "fu_missing": fu_missing,
        "fu_days_until_expiry": fu_days_until_expiry,
        "fu_expired": fu_expired,
        "fu_expiring_soon": fu_expiring_soon,
    })

    # ─── Langlieger – v4 ───
    langlieger_warn = days_since_admission >= 25 and discharge_date is None
    langlieger_critical = days_since_admission >= 28 and discharge_date is None
    langlieger_week: int | None = None
    langlieger_next_threshold: int | None = None
    if langlieger_critical:
        steps_past = max(0, (days_since_admission - 28) // 14)
        langlieger_week = 4 + steps_past * 2  # Wochen 4, 6, 8, 10...
        langlieger_next_threshold = 28 + (steps_past + 1) * 14  # 42, 56, 70...
    elif langlieger_warn:
        langlieger_week = None
        langlieger_next_threshold = 28

    out["_derived"].update({
        "langlieger_warn": langlieger_warn,
        "langlieger_critical": langlieger_critical,
        "langlieger_week": langlieger_week,
        "langlieger_next_threshold": langlieger_next_threshold,
        # v5.1: Fälle verschwinden nicht mehr, aber markiert
        "days_from_discharge": (today - discharge_date).days if discharge_date else None,
    })

    # ─── SpiGes Vollständigkeits-Checks – v4 ───
    zivilstand = c.get("zivilstand")
    zivilstand_missing = zivilstand is None
    zivilstand_unknown = str(zivilstand).strip().lower() in ("unbekannt", "9") if zivilstand else False
    aufenthaltsort_missing = c.get("aufenthaltsort_vor_eintritt") is None
    schulbildung_missing = c.get("schulbildung") is None

    # Beschäftigung: Aggregat – mind. 1 der 7 Felder = 1 (ja)
    besch_fields = [
        c.get("beschaeftigung_teilzeit"), c.get("beschaeftigung_vollzeit"),
        c.get("beschaeftigung_arbeitslos"), c.get("beschaeftigung_haushalt"),
        c.get("beschaeftigung_ausbildung"), c.get("beschaeftigung_reha"),
        c.get("beschaeftigung_iv"),
    ]
    all_none = all(v is None for v in besch_fields)
    any_yes = any(v == 1 for v in besch_fields if v is not None)
    beschaeftigung_missing = all_none or (not any_yes and not all_none)

    einweisende_instanz_missing = c.get("einweisende_instanz") is None
    behandlungsgrund_missing = c.get("behandlungsgrund") is None

    # Austritt-Felder (nur wenn discharge_date gesetzt)
    has_discharge = discharge_date is not None
    entscheid_austritt_missing = has_discharge and c.get("entscheid_austritt") is None
    aufenthalt_nach_austritt_missing = has_discharge and c.get("aufenthalt_nach_austritt") is None
    behandlung_nach_austritt_missing = has_discharge and c.get("behandlung_nach_austritt") is None
    behandlungsbereich_missing = has_discharge and c.get("behandlungsbereich") is None

    # Gruppen-Aggregate
    spiges_person_incomplete = any([zivilstand_missing, zivilstand_unknown, aufenthaltsort_missing, beschaeftigung_missing, schulbildung_missing])
    spiges_eintritt_incomplete = any([einweisende_instanz_missing, behandlungsgrund_missing])
    spiges_austritt_incomplete = has_discharge and any([entscheid_austritt_missing, aufenthalt_nach_austritt_missing, behandlung_nach_austritt_missing, behandlungsbereich_missing])

    out["_derived"].update({
        "zivilstand_missing": zivilstand_missing,
        "zivilstand_unknown": zivilstand_unknown,
        "aufenthaltsort_missing": aufenthaltsort_missing,
        "schulbildung_missing": schulbildung_missing,
        "beschaeftigung_missing": beschaeftigung_missing,
        "einweisende_instanz_missing": einweisende_instanz_missing,
        "behandlungsgrund_missing": behandlungsgrund_missing,
        "entscheid_austritt_missing": entscheid_austritt_missing,
        "aufenthalt_nach_austritt_missing": aufenthalt_nach_austritt_missing,
        "behandlung_nach_austritt_missing": behandlung_nach_austritt_missing,
        "behandlungsbereich_missing": behandlungsbereich_missing,
        "spiges_person_incomplete": spiges_person_incomplete,
        "spiges_eintritt_incomplete": spiges_eintritt_incomplete,
        "spiges_austritt_incomplete": spiges_austritt_incomplete,
    })

    # ─── SpiGes Behandlungsdaten MP 3.4 – v5 ───
    behandlung_typ_missing = c.get("behandlung_typ") is None
    # Psychopharmaka: analog Beschäftigung — mind. 1 Feld beantwortet (ja/nein)
    pharma_fields = [
        c.get("neuroleptika"), c.get("depotneuroleptika"), c.get("antidepressiva"),
        c.get("tranquilizer"), c.get("hypnotika"), c.get("psychostimulanzien"),
        c.get("suchtaversionsmittel"), c.get("lithium"), c.get("antiepileptika"),
        c.get("andere_psychopharmaka"), c.get("keine_psychopharmaka"),
    ]
    pharma_all_none = all(v is None for v in pharma_fields)
    pharma_any_answered = any(v is not None for v in pharma_fields)
    psychopharmaka_missing = pharma_all_none  # kein einziges Feld ausgefüllt

    # MB Minimaldaten
    eintrittsart_missing = c.get("eintrittsart") is None
    klasse_missing = c.get("klasse") is None

    spiges_behandlung_incomplete = any([behandlung_typ_missing, psychopharmaka_missing])

    out["_derived"].update({
        "behandlung_typ_missing": behandlung_typ_missing,
        "psychopharmaka_missing": psychopharmaka_missing,
        "eintrittsart_missing": eintrittsart_missing,
        "klasse_missing": klasse_missing,
        "spiges_behandlung_incomplete": spiges_behandlung_incomplete,
    })
    out["case_status"] = case_status
    out["responsible_person"] = c.get("responsible_person")
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
                # Fallstatus (v3)
                "case_status": c.case_status,
                "responsible_person": c.responsible_person,
                # SpiGes Personendaten (v4)
                "zivilstand": c.zivilstand,
                "aufenthaltsort_vor_eintritt": c.aufenthaltsort_vor_eintritt,
                "beschaeftigung_teilzeit": c.beschaeftigung_teilzeit,
                "beschaeftigung_vollzeit": c.beschaeftigung_vollzeit,
                "beschaeftigung_arbeitslos": c.beschaeftigung_arbeitslos,
                "beschaeftigung_haushalt": c.beschaeftigung_haushalt,
                "beschaeftigung_ausbildung": c.beschaeftigung_ausbildung,
                "beschaeftigung_reha": c.beschaeftigung_reha,
                "beschaeftigung_iv": c.beschaeftigung_iv,
                "schulbildung": c.schulbildung,
                # SpiGes Eintrittsmerkmale (v4)
                "einweisende_instanz": c.einweisende_instanz,
                "behandlungsgrund": c.behandlungsgrund,
                # SpiGes Austrittsmerkmale (v4)
                "entscheid_austritt": c.entscheid_austritt,
                "aufenthalt_nach_austritt": c.aufenthalt_nach_austritt,
                "behandlung_nach_austritt": c.behandlung_nach_austritt,
                "behandlungsbereich": c.behandlungsbereich,
                # FU (v4)
                "fu_bei_eintritt": c.fu_bei_eintritt,
                "fu_typ": c.fu_typ,
                "fu_datum": c.fu_datum,
                "fu_gueltig_bis": c.fu_gueltig_bis,
                "fu_nummer": c.fu_nummer,
                "fu_einweisende_instanz": c.fu_einweisende_instanz,
                # SpiGes Behandlungsdaten MP 3.4 (v5)
                "behandlung_typ": c.behandlung_typ,
                "neuroleptika": c.neuroleptika,
                "depotneuroleptika": c.depotneuroleptika,
                "antidepressiva": c.antidepressiva,
                "tranquilizer": c.tranquilizer,
                "hypnotika": c.hypnotika,
                "psychostimulanzien": c.psychostimulanzien,
                "suchtaversionsmittel": c.suchtaversionsmittel,
                "lithium": c.lithium,
                "antiepileptika": c.antiepileptika,
                "andere_psychopharmaka": c.andere_psychopharmaka,
                "keine_psychopharmaka": c.keine_psychopharmaka,
                # MB Minimaldaten (v5)
                "eintrittsart": c.eintrittsart,
                "klasse": c.klasse,
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
    """Alle Fälle einer Station laden (kein Auto-Hide mehr seit v5.1)."""
    return _load_raw_cases_from_db(station_id)


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
                # Fallstatus (v3)
                case_status=c.get("case_status"),
                responsible_person=c.get("responsible_person"),
                # SpiGes Personendaten (v4)
                zivilstand=c.get("zivilstand"),
                aufenthaltsort_vor_eintritt=c.get("aufenthaltsort_vor_eintritt"),
                beschaeftigung_teilzeit=c.get("beschaeftigung_teilzeit"),
                beschaeftigung_vollzeit=c.get("beschaeftigung_vollzeit"),
                beschaeftigung_arbeitslos=c.get("beschaeftigung_arbeitslos"),
                beschaeftigung_haushalt=c.get("beschaeftigung_haushalt"),
                beschaeftigung_ausbildung=c.get("beschaeftigung_ausbildung"),
                beschaeftigung_reha=c.get("beschaeftigung_reha"),
                beschaeftigung_iv=c.get("beschaeftigung_iv"),
                schulbildung=c.get("schulbildung"),
                # SpiGes Eintrittsmerkmale (v4)
                einweisende_instanz=c.get("einweisende_instanz"),
                behandlungsgrund=c.get("behandlungsgrund"),
                # SpiGes Austrittsmerkmale (v4)
                entscheid_austritt=c.get("entscheid_austritt"),
                aufenthalt_nach_austritt=c.get("aufenthalt_nach_austritt"),
                behandlung_nach_austritt=c.get("behandlung_nach_austritt"),
                behandlungsbereich=c.get("behandlungsbereich"),
                # FU (v4)
                fu_bei_eintritt=c.get("fu_bei_eintritt"),
                fu_typ=c.get("fu_typ"),
                fu_datum=_date_to_str(c.get("fu_datum")),
                fu_gueltig_bis=_date_to_str(c.get("fu_gueltig_bis")),
                fu_nummer=c.get("fu_nummer"),
                fu_einweisende_instanz=c.get("fu_einweisende_instanz"),
                # SpiGes Behandlung MP 3.4 (v5)
                behandlung_typ=c.get("behandlung_typ"),
                neuroleptika=c.get("neuroleptika"),
                depotneuroleptika=c.get("depotneuroleptika"),
                antidepressiva=c.get("antidepressiva"),
                tranquilizer=c.get("tranquilizer"),
                hypnotika=c.get("hypnotika"),
                psychostimulanzien=c.get("psychostimulanzien"),
                suchtaversionsmittel=c.get("suchtaversionsmittel"),
                lithium=c.get("lithium"),
                antiepileptika=c.get("antiepileptika"),
                andere_psychopharmaka=c.get("andere_psychopharmaka"),
                keine_psychopharmaka=c.get("keine_psychopharmaka"),
                # MB Minimaldaten (v5)
                eintrittsart=c.get("eintrittsart"),
                klasse=c.get("klasse"),
                source="demo",
            )
            db.merge(case)
        db.commit()
        print(f"{len(DUMMY_CASES)} Demo-Faelle in DB importiert")
