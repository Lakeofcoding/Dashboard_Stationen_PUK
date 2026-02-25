"""
BI-Analytics-Modul — Dedizierte Auswertungslogik für das Direktions-Dashboard.

ARCHITEKTUR:
  Dieses Modul enthält ALLE Berechnungen für die BI-Auswertung.
  Es ist bewusst als eigenständiger, erweiterbarer Block implementiert.

  Berechnung auf EINZELFALL-Ebene:
    Station A: 3/5 HoNOS + Station B: 8/10 HoNOS → 11/15 = 73.3%
    (= "11 von 15 Fällen haben HoNOS ausgefüllt")

ERWEITERUNG:
  1. Neue Quota hinzufügen: COMPLETENESS_QUOTAS-Liste erweitern
  2. Neue Metrik: In compute_station_analytics() ergänzen
  3. Neue Kennzahl: compute_station_analytics() Return-Dict erweitern
     → Frontend: AnalyticsPanel.tsx StationAnalytics-Type anpassen

Abhängigkeiten:
  - case_logic.enrich_case: Anreicherung der Rohdaten
  - rule_engine.evaluate_alerts: Regelauswertung
  - models.Ack: ACK-Aktivität aus DB
"""
from __future__ import annotations
from datetime import datetime
from app.rule_engine import evaluate_alerts
from app.db import SessionLocal
from app.models import Ack
from app.config import STATION_CENTER


# ═══════════════════════════════════════════════════════════════════════
# COMPLETENESS QUOTAS — Übergruppen-Definitionen
# ═══════════════════════════════════════════════════════════════════════
#
# Jede Quota: (key, label, check_fn, applies_to_open, applies_to_closed)
#
# check_fn bekommt einen ENRICHED case-dict und gibt True/False zurück.
# Das Frontend schaltet per Toggle zwischen offenen und geschlossenen Fällen.
# ═══════════════════════════════════════════════════════════════════════

def _q_honos(c: dict) -> bool:
    """HoNOS: Eintritt bei offenen, Eintritt+Austritt bei geschlossenen."""
    if c.get("discharge_date") is None:
        return c.get("honos_entry_total") is not None
    return (c.get("honos_entry_total") is not None
            and c.get("honos_discharge_total") is not None)


def _q_bscl(c: dict) -> bool:
    """BSCL: Eintritt bei offenen, Eintritt+Austritt bei geschlossenen."""
    if c.get("discharge_date") is None:
        return c.get("bscl_total_entry") is not None
    return (c.get("bscl_total_entry") is not None
            and c.get("bscl_discharge_total") is not None)


def _q_bfs(c: dict) -> bool:
    """BFS Verlauf: Alle 3 BFS-Werte vorhanden."""
    return c.get("_derived", {}).get("bfs_complete", False)


def _q_treatment_plan(c: dict) -> bool:
    """Behandlungsplan vorhanden."""
    return c.get("treatment_plan_date") is not None


def _q_spiges_stamm(c: dict) -> bool:
    """SpiGes Stammdaten: Alle Pflichtfelder ausgefüllt."""
    for f in ("zivilstand", "aufenthaltsort_vor_eintritt", "beschaeftigung_1",
              "schulbildung", "einweisende_instanz"):
        if c.get(f) is None:
            return False
    return True


def _q_spiges_austritt(c: dict) -> bool:
    """SpiGes Austritt: Alle Austrittsfelder ausgefüllt."""
    for f in ("entscheid_austritt", "aufenthalt_nach_austritt", "behandlung_nach_austritt"):
        if c.get(f) is None:
            return False
    return True


def _q_psychopharmaka(c: dict) -> bool:
    """Psychopharmaka: Mindestens ein Medikamentenfeld dokumentiert."""
    fields = [
        "neuroleptika", "depotneuroleptika", "antidepressiva", "tranquilizer",
        "hypnotika", "psychostimulanzien", "suchtaversionsmittel", "lithium",
        "antiepileptika", "andere_psychopharmaka", "keine_psychopharmaka",
    ]
    return any(c.get(f) is not None for f in fields)


def _q_fu(c: dict) -> bool:
    """FU-Anordnung vorhanden."""
    return c.get("fu_start") is not None


def _q_doc_austritt(c: dict) -> bool:
    """Dokumentationsabschluss nach Austritt erledigt."""
    return c.get("doc_completion_date") is not None


# ── Quota-Registry ────────────────────────────────────────────────────
# ERWEITERUNG: Neue Zeile hier einfügen.
# Format: (key, label, check_fn, applies_to_open, applies_to_closed)
COMPLETENESS_QUOTAS: list[tuple[str, str, callable, str]] = [
    # (key, label, check_fn, category)
    # category: "ongoing" = laufend relevant, "exit" = erst bei Austritt fällig
    ("honos",           "HoNOS",              _q_honos,          "ongoing"),
    ("bscl",            "BSCL",               _q_bscl,           "ongoing"),
    ("bfs",             "BFS Verlauf",         _q_bfs,            "ongoing"),
    ("treatment_plan",  "Behandlungsplan",     _q_treatment_plan, "ongoing"),
    ("spiges_stamm",    "SpiGes Stammdaten",   _q_spiges_stamm,   "ongoing"),
    ("psychopharmaka",  "Psychopharmaka",      _q_psychopharmaka, "ongoing"),
    ("fu",              "FU-Anordnung",        _q_fu,             "ongoing"),
    ("spiges_austritt", "SpiGes Austritt",     _q_spiges_austritt,"exit"),
    ("doc_austritt",    "Dok Austritt",        _q_doc_austritt,   "exit"),
]


# ═══════════════════════════════════════════════════════════════════════
# HAUPTBERECHNUNG
# ═══════════════════════════════════════════════════════════════════════

def compute_station_analytics(station_id: str, cases: list[dict], clinic: str) -> dict:
    """Berechnet alle BI-Metriken für eine Station.

    Args:
        station_id: z.B. "Station G0"
        cases: Enriched case-dicts (output von get_station_cases)
        clinic: Klinik-Kürzel (z.B. "EPP")

    Returns:
        Dict mit: total/open/closed_cases, completeness_dist, doc_reports,
        ack_this_month, completeness_quotas, top_rules
    """
    open_cases = [c for c in cases if c.get("discharge_date") is None]
    closed_cases = [c for c in cases if c.get("discharge_date") is not None]

    # ── 1. Vollständigkeits-Verteilung (pro Fall: hat Alerts?) ────────
    comp_dist = {"complete": 0, "incomplete": 0}
    # Severity-Verteilung: critical / warn / ok
    severity_dist = {"critical": 0, "warn": 0, "ok": 0}
    rule_hits: dict[str, dict] = {}
    langlieger_count = 0  # Offene Fälle ≥ 50 Tage

    for c in cases:
        # Cases sind bereits enriched (von get_station_cases)
        alerts = evaluate_alerts(c)
        if alerts:
            comp_dist["incomplete"] += 1
        else:
            comp_dist["complete"] += 1

        # Severity pro Fall
        has_crit = any(a.severity == "CRITICAL" for a in alerts)
        has_warn = any(a.severity == "WARN" for a in alerts)
        if has_crit:
            severity_dist["critical"] += 1
        elif has_warn:
            severity_dist["warn"] += 1
        else:
            severity_dist["ok"] += 1

        for a in alerts:
            if a.rule_id not in rule_hits:
                rule_hits[a.rule_id] = {
                    "count": 0, "message": a.message,
                    "category": a.category, "severity": a.severity,
                }
            rule_hits[a.rule_id]["count"] += 1

    # Langlieger: offene Fälle ≥ 50 Tage
    for c in open_cases:
        days = (c.get("_derived") or {}).get("days_since_admission", 0)
        if days >= 50:
            langlieger_count += 1

    # ── 2. Austrittsberichte ──────────────────────────────────────────
    doc_within_time = 0   # offen, < 10 Tage
    doc_overdue = 0       # offen, ≥ 10 Tage
    doc_done = 0          # abgeschlossen
    overdue_by_person: dict[str, int] = {}

    for c in closed_cases:
        # Cases sind bereits enriched (von get_station_cases)
        derived = c.get("_derived", {})
        cs = c.get("case_status", "")

        if cs == "Dokumentation abgeschlossen" or c.get("doc_completion_date"):
            doc_done += 1
        elif derived.get("doc_completion_overdue"):
            doc_overdue += 1
            person = c.get("responsible_person") or "Unbekannt"
            overdue_by_person[person] = overdue_by_person.get(person, 0) + 1
        elif derived.get("doc_completion_warn") or cs == "Dokumentation offen":
            doc_within_time += 1

    overdue_persons = sorted(overdue_by_person.items(), key=lambda x: -x[1])[:10]

    # ── 3. Completeness Quotas — auf Einzelfall-Ebene ─────────────────
    quotas = []
    for key, label, check_fn, category in COMPLETENESS_QUOTAS:
        open_total = len(open_cases)
        open_filled = sum(1 for c in open_cases if check_fn(c))
        closed_total = len(closed_cases)
        closed_filled = sum(1 for c in closed_cases if check_fn(c))

        quotas.append({
            "key": key, "label": label, "category": category,
            "open_filled": open_filled, "open_total": open_total,
            "open_pct": round(open_filled / open_total * 100, 1) if open_total > 0 else None,
            "closed_filled": closed_filled, "closed_total": closed_total,
            "closed_pct": round(closed_filled / closed_total * 100, 1) if closed_total > 0 else None,
        })

    # ── 4. ACK-Aktivität diesen Monat ─────────────────────────────────
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    with SessionLocal() as db:
        month_acks = db.query(Ack).filter(
            Ack.station_id == station_id,
            Ack.ack_scope == "rule",
            Ack.acked_at >= month_start,
        ).all()
    ack_count = sum(1 for a in month_acks if getattr(a, "action", "ACK") == "ACK")
    shift_count = sum(1 for a in month_acks if getattr(a, "action", None) == "SHIFT")

    # ── 5. Top-Regelverstösse ─────────────────────────────────────────
    top_rules = sorted(rule_hits.items(), key=lambda x: -x[1]["count"])[:10]

    # ── Return ────────────────────────────────────────────────────────
    return {
        "station_id": station_id,
        "center": STATION_CENTER.get(station_id, "UNKNOWN"),
        "clinic": clinic,
        "total_cases": len(cases),
        "open_cases": len(open_cases),
        "closed_cases": len(closed_cases),
        "completeness_dist": comp_dist,
        "severity_dist": severity_dist,
        "langlieger_count": langlieger_count,
        "doc_reports": {
            "done": doc_done,
            "within_time": doc_within_time,
            "overdue": doc_overdue,
            "overdue_by_person": [{"person": p, "count": n} for p, n in overdue_persons],
        },
        "ack_this_month": {"ack_count": ack_count, "shift_count": shift_count},
        "completeness_quotas": quotas,
        "top_rules": [
            {"rule_id": rid, "count": info["count"], "message": info["message"],
             "category": info["category"], "severity": info["severity"]}
            for rid, info in top_rules
        ],
    }
