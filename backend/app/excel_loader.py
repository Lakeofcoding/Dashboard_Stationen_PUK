"""
Excel-basierter Datenloader fuer Demo-/Testdaten.

Liest `backend/data/demo_cases.xlsx` und stellt bereit:
  - Falldaten im gleichen dict-Format wie die bisherigen DUMMY_CASES
  - Verlaufsdaten fuer Clozapin-Labor und EKG (fuer Charts)
  - Stations-/Klinik-Zuordnung

Die Excel kann jederzeit ausgetauscht werden; beim naechsten Server-Start
werden die neuen Daten geladen.

Fuer Produktiv: PostgreSQL-Views ersetzen diesen Loader (siehe config.DATA_SOURCE).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _HAS_PANDAS = False

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_EXCEL_PATH = os.getenv("DASHBOARD_DEMO_EXCEL", str(_DATA_DIR / "demo_cases.xlsx"))

# ─── Cache ───
_cases: list[dict] | None = None
_lab_history: dict[str, list[dict]] | None = None
_ekg_history: dict[str, list[dict]] | None = None
_station_map: dict[str, dict] | None = None
_efm_events: dict[str, list[dict]] | None = None
_one_to_one: dict[str, list[dict]] | None = None


def _is_na(v: Any) -> bool:
    """Prueft auf NaN/NaT/None — funktioniert mit und ohne pandas."""
    if v is None:
        return True
    if _HAS_PANDAS:
        try:
            return bool(pd.isna(v))
        except (TypeError, ValueError):
            return False
    # Ohne pandas: float NaN + string checks
    if isinstance(v, float):
        import math
        return math.isnan(v)
    if isinstance(v, str) and v.strip().lower() in ("nat", "nan", "none", ""):
        return True
    return False


def _to_date(v: Any) -> date | None:
    if _is_na(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s or s.lower() in ("nat", "nan", "none", ""):
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _to_float(v: Any) -> float | None:
    if _is_na(v):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_int(v: Any) -> int | None:
    f = _to_float(v)
    return int(f) if f is not None else None


def _to_str(v: Any) -> str | None:
    if _is_na(v):
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nat", "nan", "none") else None


def _to_bool(v: Any, default: bool = True) -> bool:
    if _is_na(v):
        return default
    s = str(v).strip().lower()
    return s in ("ja", "yes", "true", "1")


# ═══════════════════════════════════════════════════════════════
# Station / Klinik mapping
# ═══════════════════════════════════════════════════════════════

def load_station_map() -> dict[str, dict]:
    """Laedt Stations-Zuordnung: {station_id: {klinik, zentrum, beschreibung}}."""
    global _station_map
    if _station_map is not None:
        return _station_map

    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="Zuordnung Klinik")
        _station_map = {}
        for _, row in df.iterrows():
            sid = _to_str(row.iloc[0])
            if sid and not sid.startswith("_"):
                _station_map[sid] = {
                    "klinik": _to_str(row.iloc[1]) or "EPP",
                    "zentrum": _to_str(row.iloc[2]) or "UNKNOWN",
                    "beschreibung": _to_str(row.iloc[3]) or sid,
                }
    except Exception as e:
        print(f"[excel_loader] Zuordnung Klinik nicht geladen: {e}")
        _station_map = {}

    return _station_map


def get_station_center_map() -> dict[str, str]:
    """Gibt {station_id: zentrum} zurueck (kompatibel mit config.STATION_CENTER)."""
    sm = load_station_map()
    return {sid: info["zentrum"] for sid, info in sm.items()}


def get_station_klinik_map() -> dict[str, str]:
    """Gibt {station_id: klinik} zurueck."""
    sm = load_station_map()
    return {sid: info["klinik"] for sid, info in sm.items()}


# ═══════════════════════════════════════════════════════════════
# Case loading from HoNOS_BSCL + Clozapin + EKG sheets
# ═══════════════════════════════════════════════════════════════

def _load_cases_from_excel() -> list[dict]:
    """Hauptlader: liest HoNOS_BSCL und merged mit Clozapin + EKG fuer Snapshot-Werte."""
    if not _HAS_PANDAS:
        print("[excel_loader] pandas/openpyxl nicht verfuegbar – pip install pandas openpyxl")
        return []
    if not os.path.exists(_EXCEL_PATH):
        print(f"[excel_loader] {_EXCEL_PATH} nicht gefunden, keine Demo-Daten.")
        return []

    sm = load_station_map()
    center_map = get_station_center_map()
    klinik_map = get_station_klinik_map()

    # ─── HoNOS / BSCL (Hauptblatt) ───
    df_honos = pd.read_excel(_EXCEL_PATH, sheet_name="HoNOS_BSCL")
    cases_by_fnr: dict[int, dict] = {}
    for _, r in df_honos.iterrows():
        fnr = r.get("Fallnummer")
        if _is_na(fnr):
            continue
        fnr = int(fnr)
        station = _to_str(r.get("Station")) or "UNKNOWN"
        klinik = _to_str(r.get("Klinik")) or klinik_map.get(station, "EPP")
        zentrum = _to_str(r.get("Zentrum")) or center_map.get(station, "UNKNOWN")
        adm = _to_date(r.get("Eintrittsdatum"))
        dis = _to_date(r.get("Austrittsdatum"))

        cases_by_fnr[fnr] = {
            "case_id": str(fnr),
            "patient_id": f"P{fnr}",
            "clinic": klinik,
            "station_id": station,
            "center": zentrum,
            "admission_date": adm or date.today(),
            "discharge_date": dis,
            "is_voluntary": _to_bool(r.get("Freiwillig (FU)"), default=True),
            "honos_entry_total": _to_int(r.get("HoNOS Eintrittsscore")),
            "honos_entry_date": _to_date(r.get("HoNOS Erfassungsdatum Eintritt")),
            "honos_discharge_total": _to_int(r.get("HoNOS/CA Austrittsscore")),
            "honos_discharge_date": _to_date(r.get("HoNOS Erfassungsdatum Austritt")),
            "honos_discharge_suicidality": _to_int(r.get("HoNOS Austritt Suizidalität")),
            "bscl_total_entry": _to_float(r.get("BSCL Eintrittsscore")),
            "bscl_entry_date": _to_date(r.get("BSCL Erfassungsdatum Eintritt")),
            "bscl_total_discharge": _to_float(r.get("BSCL Austrittsscore")),
            "bscl_discharge_date": _to_date(r.get("BSCL Erfassungsdatum Austritt")),
            "bscl_discharge_suicidality": _to_int(r.get("BSCL Austritt Suizidalität")),
            # Defaults — will be overridden below
            "bfs_1": None, "bfs_2": None, "bfs_3": None,
            "isolations": [],
            "treatment_plan_date": None, "sdep_complete": None,
            "ekg_last_date": None, "ekg_last_reported": None, "ekg_entry_date": None,
            "clozapin_active": False, "clozapin_start_date": None,
            "neutrophils_last_date": None, "neutrophils_last_value": None,
            "troponin_last_date": None, "cbc_last_date": None,
            "emergency_bem_start_date": None, "emergency_med_start_date": None,
            "allergies_recorded": True,
            # Fallstatus & Verantwortlichkeit (v3)
            "case_status": _to_str(r.get("Fallstatus")),
            "responsible_person": _to_str(r.get("Fallführende Person")),
            # SpiGes Personendaten (v4) – Defaults, ggf. aus BFS_SPIGES überschrieben
            "zivilstand": None, "aufenthaltsort_vor_eintritt": None,
            "beschaeftigung_teilzeit": None, "beschaeftigung_vollzeit": None,
            "beschaeftigung_arbeitslos": None, "beschaeftigung_haushalt": None,
            "beschaeftigung_ausbildung": None, "beschaeftigung_reha": None,
            "beschaeftigung_iv": None, "schulbildung": None,
            # SpiGes Eintrittsmerkmale (v4)
            "einweisende_instanz": None, "behandlungsgrund": None,
            # SpiGes Austrittsmerkmale (v4)
            "entscheid_austritt": None, "aufenthalt_nach_austritt": None,
            "behandlung_nach_austritt": None, "behandlungsbereich": None,
            # FU (v4)
            "fu_bei_eintritt": _to_str(r.get("FU bei Eintritt")),
            "fu_typ": _to_str(r.get("FU Typ")),
            "fu_datum": _to_date(r.get("FU Datum")),
            "fu_gueltig_bis": _to_date(r.get("FU gültig bis")),
            "fu_nummer": _to_int(r.get("FU Nummer")),
            "fu_einweisende_instanz": _to_str(r.get("FU Einweisende Instanz")),
            # SpiGes Behandlungsdaten MP 3.4 (v5)
            "behandlung_typ": None, "neuroleptika": None, "depotneuroleptika": None,
            "antidepressiva": None, "tranquilizer": None, "hypnotika": None,
            "psychostimulanzien": None, "suchtaversionsmittel": None,
            "lithium": None, "antiepileptika": None,
            "andere_psychopharmaka": None, "keine_psychopharmaka": None,
            # MB Minimaldaten (v5)
            "eintrittsart": None, "klasse": None,
        }

    # ─── Fallback: Auto-Ableitung falls Excel-Spalten leer ───
    for fnr, c in cases_by_fnr.items():
        if not c.get("case_status"):
            c["case_status"] = "Fall offen" if c["discharge_date"] is None else "Dokumentation abgeschlossen"

    # ─── Clozapin (Snapshot-Werte fuer Rule-Engine) ───
    try:
        df_cloz = pd.read_excel(_EXCEL_PATH, sheet_name="Clozapin")
        for _, r in df_cloz.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr not in cases_by_fnr:
                continue
            c = cases_by_fnr[fnr]
            active = _to_bool(r.get("Clozapin aktiv"), default=False)
            c["clozapin_active"] = active
            if active:
                c["clozapin_start_date"] = _to_date(r.get("Clozapin Startdatum"))
                c["neutrophils_last_value"] = _to_str(r.get("Neutrophile (G/l)"))
                c["neutrophils_last_date"] = _to_date(r.get("Neutrophile Datum"))
                c["cbc_last_date"] = _to_date(r.get("Grosses Blutbild Datum"))
                c["troponin_last_date"] = _to_date(r.get("Troponin Datum"))
    except Exception as e:
        print(f"[excel_loader] Clozapin-Sheet: {e}")

    # ─── EKG (Snapshot-Werte fuer Rule-Engine) ───
    try:
        df_ekg = pd.read_excel(_EXCEL_PATH, sheet_name="EKG")
        for _, r in df_ekg.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr not in cases_by_fnr:
                continue
            c = cases_by_fnr[fnr]
            c["ekg_entry_date"] = _to_date(r.get("EKG Eintritt Datum"))
            c["ekg_last_date"] = _to_date(r.get("EKG letztes Datum"))
            ekg_rep = r.get("EKG letztes befundet")
            c["ekg_last_reported"] = _to_bool(ekg_rep, default=False) if ekg_rep is not None and not (isinstance(ekg_rep, float) and pd.isna(ekg_rep)) else None
    except Exception as e:
        print(f"[excel_loader] EKG-Sheet: {e}")

    # ─── BFS + SpiGes (aus BFS_SPIGES) ───
    try:
        df_bfs = pd.read_excel(_EXCEL_PATH, sheet_name="BFS_SPIGES")
        for _, r in df_bfs.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr not in cases_by_fnr:
                continue
            c = cases_by_fnr[fnr]
            # BFS (wie bisher)
            c["bfs_1"] = _to_int(r.get("1.5.V01 GAF bei Eintritt"))
            c["bfs_2"] = _to_int(r.get("1.5.V03 Symptom-Schweregrad (CGI-S) Eintritt"))
            c["bfs_3"] = _to_int(r.get("1.5.V02 GAF bei Austritt"))
            # SpiGes Personendaten (MP 3.2)
            c["zivilstand"] = _to_str(r.get("3.2.V01 Zivilstand")) or _to_str(r.get("Zivilstand")) or c["zivilstand"]
            c["aufenthaltsort_vor_eintritt"] = _to_str(r.get("3.2.V02 Aufenthaltsort")) or _to_str(r.get("Aufenthaltsort")) or c["aufenthaltsort_vor_eintritt"]
            c["beschaeftigung_teilzeit"] = _to_int(r.get("3.2.V03 Teilzeit")) if not _is_na(r.get("3.2.V03 Teilzeit")) else c["beschaeftigung_teilzeit"]
            c["beschaeftigung_vollzeit"] = _to_int(r.get("3.2.V04 Vollzeit")) if not _is_na(r.get("3.2.V04 Vollzeit")) else c["beschaeftigung_vollzeit"]
            c["beschaeftigung_arbeitslos"] = _to_int(r.get("3.2.V05 Arbeitslos")) if not _is_na(r.get("3.2.V05 Arbeitslos")) else c["beschaeftigung_arbeitslos"]
            c["beschaeftigung_haushalt"] = _to_int(r.get("3.2.V06 Haushalt")) if not _is_na(r.get("3.2.V06 Haushalt")) else c["beschaeftigung_haushalt"]
            c["beschaeftigung_ausbildung"] = _to_int(r.get("3.2.V07 Ausbildung")) if not _is_na(r.get("3.2.V07 Ausbildung")) else c["beschaeftigung_ausbildung"]
            c["beschaeftigung_reha"] = _to_int(r.get("3.2.V08 Reha")) if not _is_na(r.get("3.2.V08 Reha")) else c["beschaeftigung_reha"]
            c["beschaeftigung_iv"] = _to_int(r.get("3.2.V09 IV")) if not _is_na(r.get("3.2.V09 IV")) else c["beschaeftigung_iv"]
            c["schulbildung"] = _to_str(r.get("3.2.V10 Schulbildung")) or _to_str(r.get("Schulbildung")) or c["schulbildung"]
            # SpiGes Eintrittsmerkmale (MP 3.3)
            c["einweisende_instanz"] = _to_str(r.get("3.3.V01 Einweisende Instanz")) or _to_str(r.get("Einweisende Instanz")) or c["einweisende_instanz"]
            c["behandlungsgrund"] = _to_str(r.get("3.3.V02 Behandlungsgrund")) or _to_str(r.get("Behandlungsgrund")) or c["behandlungsgrund"]
            # FU bei Eintritt (BFS 3.3.V03)
            fu_val = _to_str(r.get("3.3.V03 FU bei Eintritt"))
            if fu_val and not c.get("fu_bei_eintritt"):
                c["fu_bei_eintritt"] = fu_val
            # SpiGes Austrittsmerkmale (MP 3.5)
            c["entscheid_austritt"] = _to_str(r.get("3.5.V01 Entscheid Austritt")) or _to_str(r.get("Entscheid Austritt")) or c["entscheid_austritt"]
            c["aufenthalt_nach_austritt"] = _to_str(r.get("3.5.V02 Aufenthalt nach Austritt")) or _to_str(r.get("Aufenthalt nach Austritt")) or c["aufenthalt_nach_austritt"]
            c["behandlung_nach_austritt"] = _to_str(r.get("3.5.V03 Behandlung nach Austritt")) or _to_str(r.get("Behandlung nach Austritt")) or c["behandlung_nach_austritt"]
            c["behandlungsbereich"] = _to_str(r.get("3.5.V04 Behandlungsbereich")) or _to_str(r.get("Behandlungsbereich")) or c["behandlungsbereich"]
            # SpiGes Behandlungsdaten (MP 3.4)
            c["behandlung_typ"] = _to_str(r.get("3.4.V02 Behandlung")) or _to_str(r.get("Behandlung")) or c.get("behandlung_typ")
            for col_suffix, field_name in [
                ("V03 Neuroleptika", "neuroleptika"), ("V04 Depotneuroleptika", "depotneuroleptika"),
                ("V05 Antidepressiva", "antidepressiva"), ("V06 Tranquilizer", "tranquilizer"),
                ("V07 Hypnotika", "hypnotika"), ("V08 Psychostimulanzien", "psychostimulanzien"),
                ("V09 Suchtaversionsmittel", "suchtaversionsmittel"), ("V10 Lithium", "lithium"),
                ("V11 Antiepileptika", "antiepileptika"), ("V12 Andere Psychopharmaka", "andere_psychopharmaka"),
                ("V13 Keine Psychopharmaka", "keine_psychopharmaka"),
            ]:
                val = r.get(f"3.4.{col_suffix}")
                if val is None:
                    val = r.get(col_suffix.split(" ", 1)[-1])  # Kurzname-Fallback
                if not _is_na(val):
                    c[field_name] = _to_int(val) if c.get(field_name) is None else c[field_name]
            # MB Minimaldaten
            c["eintrittsart"] = _to_str(r.get("1.2.V03 Eintrittsart")) or _to_str(r.get("Eintrittsart")) or c.get("eintrittsart")
            c["klasse"] = _to_str(r.get("1.3.V02 Klasse")) or _to_str(r.get("Klasse")) or c.get("klasse")
    except Exception as e:
        print(f"[excel_loader] BFS/SpiGes-Sheet: {e}")

    # ─── EFM -> Isolations-Liste ───
    try:
        df_efm = pd.read_excel(_EXCEL_PATH, sheet_name="Freiheitsbeschr. Massnahmen")
        for _, r in df_efm.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr not in cases_by_fnr:
                continue
            code = _to_int(r.get("EFM Code"))
            if code == 1:  # Isolation
                start = _to_date(r.get("Start"))
                end = _to_date(r.get("Ende"))
                iso = {"start": start.isoformat() + "T00:00:00Z" if start else None}
                if end:
                    iso["stop"] = end.isoformat() + "T00:00:00Z"
                else:
                    iso["stop"] = None
                cases_by_fnr[fnr]["isolations"].append(iso)
    except Exception as e:
        print(f"[excel_loader] EFM-Sheet: {e}")

    # ─── Instrument-Views: v_honos, v_honosca, v_bscl, v_honosca_sr ───
    # Diese Views sind die Primärquelle für alle Outcome-Daten.
    # Totals in HoNOS_BSCL werden hier ÜBERSCHRIEBEN mit berechneten Werten.
    # Später: identische Abfrage auf PostgreSQL-Views.

    def _read_view_items(sheet_name: str, n_items: int, total_col: str = "total") -> dict:
        """Liest eine View und gibt {fid: {ET: {items, total, datum}, AT: {...}}} zurück."""
        result: dict[int, dict] = {}
        try:
            df_v = pd.read_excel(_EXCEL_PATH, sheet_name=sheet_name)
            for _, r in df_v.iterrows():
                fid = _to_int(r.get("fid"))
                if fid is None:
                    continue
                zp = _to_str(r.get("zeitpunkt"))  # "ET" oder "AT"
                if zp not in ("ET", "AT"):
                    continue
                items = []
                for i in range(1, n_items + 1):
                    items.append(_to_int(r.get(f"item_{i:02d}")))
                entry = {
                    "items": items,
                    "datum": _to_date(r.get("datum")),
                    "total": _to_float(r.get(total_col)),
                    "suizidalitaet": _to_int(r.get("suizidalitaet")),
                }
                if fid not in result:
                    result[fid] = {}
                result[fid][zp] = entry
            print(f"[excel_loader] {sheet_name}: {len(df_v)} Zeilen → {len(result)} Fälle")
        except Exception as e:
            print(f"[excel_loader] {sheet_name}: {e}")
        return result

    def _sum_items(items: list) -> int | None:
        """Summiere Items, 9=not known wird ausgeschlossen."""
        vals = [v for v in items if v is not None and v != 9]
        return sum(vals) if vals else None

    # Lade alle 4 Views
    v_honos = _read_view_items("v_honos", 12, "total")
    v_honosca = _read_view_items("v_honosca", 13, "total_a")
    v_bscl = _read_view_items("v_bscl", 53, "gsi")
    v_honosca_sr = _read_view_items("v_honosca_sr", 13, "total")

    # Merge in Cases: Fremdbeurteilung (HoNOS / HoNOSCA)
    for fnr, c in cases_by_fnr.items():
        is_kjpp = c.get("clinic") == "KJPP"

        if not is_kjpp and fnr in v_honos:
            c["honos_instrument"] = "HoNOS"
            v = v_honos[fnr]
            if "ET" in v:
                c["honos_entry_items"] = v["ET"]["items"]
                c["honos_entry_total"] = v["ET"]["total"] or _sum_items(v["ET"]["items"])
                c["honos_entry_date"] = v["ET"]["datum"] or c.get("honos_entry_date")
            if "AT" in v:
                c["honos_discharge_items"] = v["AT"]["items"]
                c["honos_discharge_total"] = v["AT"]["total"] or _sum_items(v["AT"]["items"])
                c["honos_discharge_date"] = v["AT"]["datum"] or c.get("honos_discharge_date")
                if v["AT"].get("suizidalitaet") is not None:
                    c["honos_discharge_suicidality"] = v["AT"]["suizidalitaet"]

        elif is_kjpp and fnr in v_honosca:
            c["honos_instrument"] = "HoNOSCA"
            v = v_honosca[fnr]
            if "ET" in v:
                c["honos_entry_items"] = v["ET"]["items"]
                c["honos_entry_total"] = v["ET"]["total"] or _sum_items(v["ET"]["items"])
                c["honos_entry_date"] = v["ET"]["datum"] or c.get("honos_entry_date")
            if "AT" in v:
                c["honos_discharge_items"] = v["AT"]["items"]
                c["honos_discharge_total"] = v["AT"]["total"] or _sum_items(v["AT"]["items"])
                c["honos_discharge_date"] = v["AT"]["datum"] or c.get("honos_discharge_date")

    # Merge: Selbstbeurteilung (BSCL / HoNOSCA-SR)
    for fnr, c in cases_by_fnr.items():
        is_kjpp = c.get("clinic") == "KJPP"

        if not is_kjpp and fnr in v_bscl:
            v = v_bscl[fnr]
            if "ET" in v:
                c["bscl_entry_items"] = v["ET"]["items"]
                c["bscl_total_entry"] = v["ET"]["total"]  # GSI
                c["bscl_entry_date"] = v["ET"]["datum"] or c.get("bscl_entry_date")
            if "AT" in v:
                c["bscl_discharge_items"] = v["AT"]["items"]
                c["bscl_total_discharge"] = v["AT"]["total"]  # GSI
                c["bscl_discharge_date"] = v["AT"]["datum"] or c.get("bscl_discharge_date")
                if v["AT"].get("suizidalitaet") is not None:
                    c["bscl_discharge_suicidality"] = v["AT"]["suizidalitaet"]

        elif is_kjpp and fnr in v_honosca_sr:
            c["honosca_sr_instrument"] = "HoNOSCA-SR"
            v = v_honosca_sr[fnr]
            if "ET" in v:
                c["bscl_entry_items"] = v["ET"]["items"]  # mapped to bscl fields
                c["bscl_total_entry"] = round(v["ET"]["total"] / 13, 2) if v["ET"]["total"] else None
                c["bscl_entry_date"] = v["ET"]["datum"] or c.get("bscl_entry_date")
            if "AT" in v:
                c["bscl_discharge_items"] = v["AT"]["items"]
                c["bscl_total_discharge"] = round(v["AT"]["total"] / 13, 2) if v["AT"]["total"] else None
                c["bscl_discharge_date"] = v["AT"]["datum"] or c.get("bscl_discharge_date")

    return list(cases_by_fnr.values())


# ═══════════════════════════════════════════════════════════════
# Longitudinal data (fuer Charts)
# ═══════════════════════════════════════════════════════════════

def _load_lab_history() -> dict[str, list[dict]]:
    """Clozapin Laborverlauf: {case_id: [{date, neutro, leuko, spiegel, troponin, ...}]}."""
    result: dict[str, list[dict]] = {}
    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="Clozapin Laborverlauf")
        for _, r in df.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr is None:
                continue
            cid = str(fnr)
            if cid not in result:
                result[cid] = []
            result[cid].append({
                "date": (_to_date(r.get("Labordatum")) or date.today()).isoformat(),
                "week": _to_float(r.get("Woche seit Start")),
                "leuko": _to_float(r.get("Leukozyten (G/l)")),
                "neutro": _to_float(r.get("Neutrophile abs. (G/l)")),
                "neutro_pct": _to_float(r.get("Neutrophile rel. (%)")),
                "ery": _to_float(r.get("Erythrozyten (T/l)")),
                "hb": _to_float(r.get("Hämoglobin (g/l)")),
                "thrombo": _to_float(r.get("Thrombozyten (G/l)")),
                "cloz_spiegel": _to_float(r.get("Clozapin-Spiegel (ng/ml)")),
                "norclozapin": _to_float(r.get("Norclozapin (ng/ml)")),
                "troponin": _to_float(r.get("Troponin T hs (ng/l)")),
                "glukose": _to_float(r.get("Nüchternglukose (mmol/l)")),
                "hba1c": _to_float(r.get("HbA1c (%)")),
                "cholesterin": _to_float(r.get("Cholesterin total (mmol/l)")),
                "triglyzeride": _to_float(r.get("Triglyzeride (mmol/l)")),
                "alat": _to_float(r.get("ALAT/GPT (U/l)")),
                "asat": _to_float(r.get("ASAT/GOT (U/l)")),
                "crp": _to_float(r.get("CRP (mg/l)")),
                "bemerkung": _to_str(r.get("Befund/Bemerkung")),
            })
    except Exception as e:
        print(f"[excel_loader] Clozapin Laborverlauf: {e}")

    # Sort by date
    for cid in result:
        result[cid].sort(key=lambda x: x["date"])
    return result


def _load_ekg_history() -> dict[str, list[dict]]:
    """EKG Verlauf: {case_id: [{date, typ, hr, qtc, rhythmus, befund, ...}]}."""
    result: dict[str, list[dict]] = {}
    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="EKG Verlauf")
        for _, r in df.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr is None:
                continue
            cid = str(fnr)
            if cid not in result:
                result[cid] = []
            result[cid].append({
                "date": (_to_date(r.get("EKG Datum")) or date.today()).isoformat(),
                "typ": _to_str(r.get("EKG Typ")),
                "hr": _to_int(r.get("Herzfrequenz (bpm)")),
                "qtc": _to_int(r.get("QTc (ms)")),
                "qtc_method": _to_str(r.get("QTc-Methode")),
                "pq": _to_int(r.get("PQ (ms)")),
                "qrs": _to_int(r.get("QRS (ms)")),
                "rhythmus": _to_str(r.get("Rhythmus")),
                "befund": _to_str(r.get("Befund")),
                "befundet_durch": _to_str(r.get("Befundet durch")),
                "befunddatum": (_to_date(r.get("Befunddatum")) or None),
                "befunddatum_str": (_to_date(r.get("Befunddatum")) or "").isoformat() if _to_date(r.get("Befunddatum")) else None,
                "bemerkung": _to_str(r.get("Bemerkung")),
            })
    except Exception as e:
        print(f"[excel_loader] EKG Verlauf: {e}")

    for cid in result:
        result[cid].sort(key=lambda x: x["date"])
    return result


def _load_efm_events() -> dict[str, list[dict]]:
    """EFM Events: {case_id: [{code, name, group, start, end, duration, ...}]}."""
    result: dict[str, list[dict]] = {}
    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="Freiheitsbeschr. Massnahmen")
        for _, r in df.iterrows():
            fnr = _to_int(r.get("Fallnummer"))
            if fnr is None:
                continue
            cid = str(fnr)
            if cid not in result:
                result[cid] = []
            result[cid].append({
                "code": _to_int(r.get("EFM Code")),
                "name": _to_str(r.get("EFM Massnahme")),
                "group": _to_str(r.get("EFM Gruppe")),
                "start": (_to_date(r.get("Start")) or date.today()).isoformat(),
                "end": (_to_date(r.get("Ende")) or None),
                "end_str": (_to_date(r.get("Ende")) or "").isoformat() if _to_date(r.get("Ende")) else None,
                "duration_min": _to_int(r.get("Dauer (Min)")),
                "angeordnet_durch": _to_str(r.get("Angeordnet durch")),
            })
    except Exception as e:
        print(f"[excel_loader] EFM: {e}")

    for cid in result:
        result[cid].sort(key=lambda x: x["start"])
    return result


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def get_demo_cases() -> list[dict]:
    """Gibt alle Demo-Faelle als list[dict] zurueck (gecached)."""
    global _cases
    if _cases is None:
        _cases = _load_cases_from_excel()
        print(f"[excel_loader] {len(_cases)} Faelle aus {_EXCEL_PATH} geladen")
    return _cases


def get_lab_history(case_id: str) -> list[dict]:
    """Clozapin-Laborverlauf fuer einen Fall."""
    global _lab_history
    if _lab_history is None:
        _lab_history = _load_lab_history()
        total = sum(len(v) for v in _lab_history.values())
        print(f"[excel_loader] {total} Labormessungen fuer {len(_lab_history)} Faelle geladen")
    return _lab_history.get(case_id, [])


def get_ekg_history(case_id: str) -> list[dict]:
    """EKG-Verlauf fuer einen Fall."""
    global _ekg_history
    if _ekg_history is None:
        _ekg_history = _load_ekg_history()
        total = sum(len(v) for v in _ekg_history.values())
        print(f"[excel_loader] {total} EKGs fuer {len(_ekg_history)} Faelle geladen")
    return _ekg_history.get(case_id, [])


def get_efm_events(case_id: str) -> list[dict]:
    """EFM-Events fuer einen Fall."""
    global _efm_events
    if _efm_events is None:
        _efm_events = _load_efm_events()
        total = sum(len(v) for v in _efm_events.values())
        print(f"[excel_loader] {total} EFM-Events fuer {len(_efm_events)} Faelle geladen")
    return _efm_events.get(case_id, [])


# ═══════════════════════════════════════════════════════════════
# EFM Reporting (v_efm + v_sichtkontakte)
# ═══════════════════════════════════════════════════════════════

_v_efm_cache: list[dict] | None = None
_v_sichtkontakte_cache: dict[int, list[dict]] | None = None


def get_all_efm_reporting() -> list[dict]:
    """Alle EFM-Massnahmen aus v_efm (fuer Reporting). Gecached."""
    global _v_efm_cache
    if _v_efm_cache is not None:
        return _v_efm_cache
    result: list[dict] = []
    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="v_efm")
        for _, r in df.iterrows():
            fid = _to_int(r.get("fid"))
            if fid is None:
                continue
            start_d = _to_str(r.get("start_datum"))
            start_t = _to_str(r.get("start_zeit")) or "00:00"
            end_d = _to_str(r.get("end_datum"))
            end_t = _to_str(r.get("end_zeit")) or "00:00"
            start_dt = None
            end_dt = None
            try:
                if start_d:
                    start_dt = datetime.strptime(f"{start_d} {start_t}", "%Y-%m-%d %H:%M")
            except Exception:
                pass
            try:
                if end_d:
                    end_dt = datetime.strptime(f"{end_d} {end_t}", "%Y-%m-%d %H:%M")
            except Exception:
                pass
            dur_h = None
            if start_dt and end_dt:
                dur_h = round((end_dt - start_dt).total_seconds() / 3600, 1)
            result.append({
                "efm_id": _to_int(r.get("efm_id")),
                "fid": fid,
                "pid": _to_str(r.get("pid")),
                "station": _to_str(r.get("station")) or "UNKNOWN",
                "klinik": _to_str(r.get("klinik")) or "EPP",
                "zentrum": _to_str(r.get("zentrum")) or "UNKNOWN",
                "art_efm": _to_str(r.get("art_efm")) or "Unbekannt",
                "start_dt": start_dt.isoformat() if start_dt else None,
                "end_dt": end_dt.isoformat() if end_dt else None,
                "duration_h": dur_h,
                "angeordnet_von": _to_str(r.get("angeordnet_von")),
                "begruendung": _to_str(r.get("begruendung")),
            })
        print(f"[excel_loader] v_efm: {len(result)} EFM-Massnahmen geladen")
    except Exception as e:
        print(f"[excel_loader] v_efm: {e}")
    _v_efm_cache = result
    return result


def get_sichtkontakte() -> dict[int, list[dict]]:
    """Sichtkontakte aus v_sichtkontakte: {efm_id: [{zeitpunkt, bemerkung, ...}]}. Gecached."""
    global _v_sichtkontakte_cache
    if _v_sichtkontakte_cache is not None:
        return _v_sichtkontakte_cache
    result: dict[int, list[dict]] = {}
    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="v_sichtkontakte")
        for _, r in df.iterrows():
            eid = _to_int(r.get("efm_id"))
            if eid is None:
                continue
            zp_str = _to_str(r.get("zeitpunkt"))
            zp_dt = None
            try:
                if zp_str:
                    zp_dt = datetime.strptime(zp_str, "%Y-%m-%d %H:%M")
            except Exception:
                pass
            entry = {
                "sk_id": _to_int(r.get("sk_id")),
                "efm_id": eid,
                "fid": _to_int(r.get("fid")),
                "zeitpunkt": zp_dt.isoformat() if zp_dt else zp_str,
                "bemerkung": _to_str(r.get("bemerkung")),
                "durchgefuehrt_von": _to_str(r.get("durchgefuehrt_von")),
            }
            result.setdefault(eid, []).append(entry)
        total = sum(len(v) for v in result.values())
        print(f"[excel_loader] v_sichtkontakte: {total} Kontakte fuer {len(result)} EFM geladen")
    except Exception as e:
        print(f"[excel_loader] v_sichtkontakte: {e}")
    _v_sichtkontakte_cache = result
    return result


def reload():
    """Cache leeren — wird beim naechsten Zugriff neu geladen."""
    global _cases, _lab_history, _ekg_history, _station_map, _efm_events, _v_efm_cache, _v_sichtkontakte_cache
    _cases = None
    _lab_history = None
    _ekg_history = None
    _station_map = None
    _efm_events = None
    _v_efm_cache = None
    _v_sichtkontakte_cache = None
    print("[excel_loader] Cache geleert, wird beim naechsten Zugriff neu geladen.")
