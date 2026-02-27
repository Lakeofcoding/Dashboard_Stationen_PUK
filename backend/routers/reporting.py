"""
Reporting-Endpoints: HoNOS / HoNOSCA / BSCL Outcome-Reporting v4.

Datenarchitektur:
  Primärquellen (Views/Sheets):
    v_honos      → 12 Items, Erwachsene, Fremdbeurteilung
    v_honosca    → 13+2 Items, KJPP, Fremdbeurteilung
    v_bscl       → 53 Items, Erwachsene, Selbstbeurteilung
    v_honosca_sr → 13 Items, KJPP, Selbstbeurteilung

  Abgeleitetes Sheet:
    HoNOS_BSCL   → Totals, berechnet aus obigen Views

  Später: identische Views in PostgreSQL.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from app.auth import AuthContext, get_auth_context
from app.case_logic import get_all_cases_enriched
from app.bi_analytics import _q_honos
from app.excel_loader import get_station_klinik_map, get_station_center_map
from typing import Optional

router = APIRouter()

# ══════════════════════════════════════════════════════════════
# Offizielle Item-Bezeichnungen (ANQ-konform, deutsch)
# ══════════════════════════════════════════════════════════════

HONOS_ITEM_LABELS = {
    1:  "Überaktives, aggressives, Unruhe stiftendes oder agitiertes Verhalten",
    2:  "Absichtliche Selbstverletzung",
    3:  "Problemtrinken oder Drogenkonsum",
    4:  "Kognitive Probleme",
    5:  "Körperliche Erkrankung oder Behinderung",
    6:  "Halluzinationen und Wahnphänomene",
    7:  "Depressive Stimmung",
    8:  "Andere psychische und verhaltensbezogene Probleme",
    9:  "Beziehungsprobleme",
    10: "Probleme mit alltäglichen Aktivitäten",
    11: "Probleme durch Wohnbedingungen",
    12: "Probleme mit Beschäftigung und Aktivitäten",
}
# Kurzlabels für Charts
HONOS_SHORT = {
    1: "Aggression", 2: "Selbstverletzung", 3: "Substanzkonsum", 4: "Kognition",
    5: "Körperlich", 6: "Halluz./Wahn", 7: "Depression", 8: "Andere psych.",
    9: "Beziehungen", 10: "ADL", 11: "Wohnen", 12: "Beschäftigung",
}

HONOSCA_ITEM_LABELS = {
    1:  "Störendes, antisoziales oder aggressives Verhalten",
    2:  "Überaktivität, Aufmerksamkeit oder Konzentration",
    3:  "Absichtliche Selbstverletzung",
    4:  "Alkohol-, Substanz- oder Lösungsmittelmissbrauch",
    5:  "Schulische oder sprachliche Fähigkeiten",
    6:  "Körperliche Erkrankung oder Behinderung",
    7:  "Halluzinationen, Wahnphänomene oder abnorme Wahrnehmungen",
    8:  "Nicht-organische somatische Symptome",
    9:  "Emotionale und damit zusammenhängende Symptome",
    10: "Gleichaltrigenbeziehungen",
    11: "Selbstversorgung und Unabhängigkeit",
    12: "Familienleben und Beziehungen",
    13: "Mangelhafte Schulanwesenheit",
}
HONOSCA_SHORT = {
    1: "Aggression", 2: "Überaktivität", 3: "Selbstverletzung", 4: "Substanzen",
    5: "Schule/Sprache", 6: "Körperlich", 7: "Halluz./Wahn", 8: "Somatisch",
    9: "Emotionen", 10: "Peers", 11: "Selbstversorgung", 12: "Familie", 13: "Schulbesuch",
}

BSCL_SCALES = {
    "soma": {"label": "Somatisierung",              "items": [2,7,23,29,30,33,37]},
    "zwan": {"label": "Zwanghaftigkeit",             "items": [5,15,26,27,32,36]},
    "unsi": {"label": "Unsicherheit Sozialkontakt",  "items": [20,21,22,42]},
    "depr": {"label": "Depressivität",               "items": [9,16,17,18,35,50]},
    "angs": {"label": "Ängstlichkeit",               "items": [1,12,19,38,45,49]},
    "aggr": {"label": "Aggressivität/Feindseligkeit","items": [6,13,40,41,46]},
    "phob": {"label": "Phobische Angst",             "items": [8,28,31,43,47]},
    "para": {"label": "Paranoides Denken",           "items": [4,10,24,48,51]},
    "psyc": {"label": "Psychotizismus",              "items": [3,14,34,44,53]},
}

# ── Subscale definitions (0-indexed item ranges) ──
SUBSCALES_HONOS = {
    "verhalten":         {"label": "Verhalten",         "items": [0,1,2],     "max": 12},
    "beeintraechtigung": {"label": "Beeinträchtigung",  "items": [3,4],       "max": 8},
    "symptome":          {"label": "Symptome",          "items": [5,6,7],     "max": 12},
    "soziales":          {"label": "Soziales",          "items": [8,9,10,11], "max": 16},
}
SUBSCALES_HONOSCA = {
    "verhalten":         {"label": "Verhalten",         "items": [0,1,2,3],   "max": 16},
    "beeintraechtigung": {"label": "Beeinträchtigung",  "items": [4,5],       "max": 8},
    "symptome":          {"label": "Symptome",          "items": [6,7,8],     "max": 12},
    "soziales":          {"label": "Soziales",          "items": [9,10,11,12],"max": 16},
}


@router.get("/api/reporting/meta")
def instrument_metadata():
    """Metadaten: Item-Bezeichnungen, Subskalen, BSCL-Skalen für Frontend-Labels."""
    return {
        "honos": {"items": HONOS_ITEM_LABELS, "short": HONOS_SHORT, "subscales": SUBSCALES_HONOS, "n_items": 12},
        "honosca": {"items": HONOSCA_ITEM_LABELS, "short": HONOSCA_SHORT, "subscales": SUBSCALES_HONOSCA, "n_items": 13},
        "bscl": {"scales": {k: v["label"] for k, v in BSCL_SCALES.items()}, "n_items": 53},
        "honosca_sr": {"n_items": 13},
    }


def _calc_subscale(items, indices):
    """Berechne Subskalenscore aus Items. 9=not known wird ausgeschlossen."""
    if items is None:
        return None
    vals = []
    for i in indices:
        if i < len(items) and items[i] is not None and items[i] != 9:
            vals.append(items[i])
    return sum(vals) if vals else None


def _calc_all_subscales(items, instrument):
    """Berechne alle 4 Subskalen fuer ein Item-Set."""
    defs = SUBSCALES_HONOSCA if instrument == "HoNOSCA" else SUBSCALES_HONOS
    result = {}
    for key, info in defs.items():
        result[key] = _calc_subscale(items, info["items"])
    return result


def _build_hierarchy():
    klinik_map = get_station_klinik_map() or {}
    center_map = get_station_center_map() or {}
    tree = {}
    for station, klinik in klinik_map.items():
        zentrum = center_map.get(station, "UNKNOWN")
        tree.setdefault(klinik, {}).setdefault(zentrum, []).append(station)
    return {k: {z: sorted(tree[k][z]) for z in sorted(tree[k])} for k in sorted(tree)}


@router.get("/api/reporting/honos")
def honos_report(
    ctx: AuthContext = Depends(get_auth_context),
    clinic: Optional[str] = Query(None),
    center: Optional[str] = Query(None),
    station: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    all_cases = get_all_cases_enriched()
    hierarchy = _build_hierarchy()

    cases = []
    for c in all_cases:
        if clinic and c.get("clinic") != clinic: continue
        if center and c.get("center") != center: continue
        if station and c.get("station_id") != station: continue
        if year:
            adm = c.get("admission_date")
            if adm:
                try:
                    if int(str(adm)[:4]) != year: continue
                except (ValueError, TypeError): continue
            else: continue
        cases.append(c)

    scatter, worse_list = [], []
    with_entry = with_both = improved = same = worse = 0
    diffs, entries, discharges = [], [], []
    sub_e_agg = {"verhalten": [], "beeintraechtigung": [], "symptome": [], "soziales": []}
    sub_d_agg = {"verhalten": [], "beeintraechtigung": [], "symptome": [], "soziales": []}
    clinic_data, station_data = {}, {}
    # Per-item aggregation
    item_entry_agg = {}  # {item_idx: [values]}
    item_discharge_agg = {}

    for c in cases:
        entry = c.get("honos_entry_total")
        discharge = c.get("honos_discharge_total")
        e_items = c.get("honos_entry_items")
        d_items = c.get("honos_discharge_items")
        instrument = c.get("honos_instrument", "HoNOS")

        if entry is not None:
            with_entry += 1
            entries.append(entry)

        if entry is not None and discharge is not None:
            with_both += 1
            diff = entry - discharge
            diffs.append(diff)
            discharges.append(discharge)
            if diff > 0: improved += 1
            elif diff == 0: same += 1
            else: worse += 1

            # Real subscales from items
            sub_e = _calc_all_subscales(e_items, instrument)
            sub_d = _calc_all_subscales(d_items, instrument)
            for k in sub_e_agg:
                if sub_e[k] is not None: sub_e_agg[k].append(sub_e[k])
                if sub_d[k] is not None: sub_d_agg[k].append(sub_d[k])

            # Per-item aggregation
            n_items = len(e_items) if e_items else (13 if instrument == "HoNOSCA" else 12)
            for idx in range(n_items):
                if idx not in item_entry_agg:
                    item_entry_agg[idx] = []
                    item_discharge_agg[idx] = []
                if e_items and idx < len(e_items) and e_items[idx] is not None and e_items[idx] != 9:
                    item_entry_agg[idx].append(e_items[idx])
                if d_items and idx < len(d_items) and d_items[idx] is not None and d_items[idx] != 9:
                    item_discharge_agg[idx].append(d_items[idx])

            clin = c.get("clinic", "?")
            sid = c.get("station_id", "")
            ctr = c.get("center", "")

            if clin not in clinic_data:
                clinic_data[clin] = {"n": 0, "diffs": [], "improved": 0}
            clinic_data[clin]["n"] += 1
            clinic_data[clin]["diffs"].append(diff)
            if diff > 0: clinic_data[clin]["improved"] += 1

            if sid not in station_data:
                station_data[sid] = {"n": 0, "diffs": [], "improved": 0, "clinic": clin, "center": ctr}
            station_data[sid]["n"] += 1
            station_data[sid]["diffs"].append(diff)
            if diff > 0: station_data[sid]["improved"] += 1

            scatter.append({
                "case_id": c.get("case_id"), "entry": entry, "discharge": discharge,
                "diff": diff, "clinic": clin, "station": sid, "center": ctr,
                "admission": str(c.get("admission_date", ""))[:10],
                "discharge_date": str(c.get("discharge_date", ""))[:10] if c.get("discharge_date") else None,
                "suicidality_discharge": c.get("honos_discharge_suicidality"),
                "subscales_entry": sub_e, "subscales_discharge": sub_d,
            })
            if diff < 0:
                worse_list.append({
                    "case_id": c.get("case_id"), "station": sid, "clinic": clin,
                    "center": ctr, "entry": entry, "discharge": discharge, "diff": diff,
                    "admission": str(c.get("admission_date", ""))[:10],
                    "discharge_date": str(c.get("discharge_date", ""))[:10] if c.get("discharge_date") else None,
                })

    total = len(cases)
    sd = lambda a, b: round(a / b, 1) if b else 0
    kpis = {
        "total": total, "with_entry": with_entry, "with_both": with_both,
        "improved": improved, "same": same, "worse": worse,
        "avg_diff": sd(sum(diffs), len(diffs)) if diffs else None,
        "avg_entry": sd(sum(entries), len(entries)) if entries else None,
        "avg_discharge": sd(sum(discharges), len(discharges)) if discharges else None,
        "entry_completion_pct": sd(100 * with_entry, total),
        "pair_completion_pct": sd(100 * with_both, total),
        "improved_pct": sd(100 * improved, with_both),
        "worse_pct": sd(100 * worse, with_both),
    }

    # Subscales (from real items)
    defs = SUBSCALES_HONOS  # use HoNOS labels for display
    subscales = {}
    for k in defs:
        e, d = sub_e_agg[k], sub_d_agg[k]
        subscales[k] = {
            "label": defs[k]["label"], "max": defs[k]["max"],
            "avg_entry": sd(sum(e), len(e)) if e else None,
            "avg_discharge": sd(sum(d), len(d)) if d else None,
            "avg_diff": round((sum(e)/len(e)) - (sum(d)/len(d)), 1) if e and d else None,
        }

    # Per-item averages
    items_detail = []
    for idx in sorted(item_entry_agg.keys()):
        e_vals = item_entry_agg.get(idx, [])
        d_vals = item_discharge_agg.get(idx, [])
        lbl = HONOS_SHORT.get(idx + 1, f"Item {idx+1}")
        items_detail.append({
            "item": idx + 1, "label": lbl,
            "label_full": HONOS_ITEM_LABELS.get(idx + 1, ""),
            "avg_entry": sd(sum(e_vals), len(e_vals)) if e_vals else None,
            "avg_discharge": sd(sum(d_vals), len(d_vals)) if d_vals else None,
            "avg_diff": round((sum(e_vals)/len(e_vals)) - (sum(d_vals)/len(d_vals)), 1) if e_vals and d_vals else None,
            "n": len(e_vals),
        })

    by_clinic = [{"clinic": c, "n": d["n"],
                   "avg_diff": sd(sum(d["diffs"]), len(d["diffs"])),
                   "improved_pct": sd(100 * d["improved"], d["n"])}
                  for c, d in sorted(clinic_data.items())]

    by_station = [{"station": s, "clinic": d["clinic"], "center": d["center"],
                    "n": d["n"], "avg_diff": sd(sum(d["diffs"]), len(d["diffs"])),
                    "improved_pct": sd(100 * d["improved"], d["n"])}
                   for s, d in sorted(station_data.items())]

    hist = {}
    for d in diffs:
        b = round(d)
        hist[b] = hist.get(b, 0) + 1
    histogram = [{"diff": k, "count": v} for k, v in sorted(hist.items())]

    discharged = [c for c in cases if c.get("discharge_date")]
    consistency = {
        "total_cases": total,
        "honos_complete": sum(1 for c in cases if _q_honos(c)),
        "completion_pct": sd(100 * sum(1 for c in cases if _q_honos(c)), total),
        "discharged_total": len(discharged),
        "discharged_complete": sum(1 for c in discharged if _q_honos(c)),
        "discharged_pct": sd(100 * sum(1 for c in discharged if _q_honos(c)), len(discharged)),
        "has_items": any(c.get("honos_entry_items") for c in cases),
        "source": "bi_analytics._q_honos (identische Logik)",
    }

    worse_list.sort(key=lambda x: x["diff"])

    # Data source info
    data_sources = {
        "fremdbeurteilung": "v_honos (Erwachsene) + v_honosca (KJPP)",
        "selbstbeurteilung": "v_bscl (Erwachsene) + v_honosca_sr (KJPP)",
        "totals_derived_from": "Einzelitems (nicht aus HoNOS_BSCL gelesen)",
        "subscales": "Berechnet aus echten Items, nicht geschätzt",
    }

    return {
        "scatter": scatter, "kpis": kpis, "subscales": subscales,
        "items_detail": items_detail,
        "by_clinic": by_clinic, "by_station": by_station,
        "histogram": histogram, "worse_list": worse_list,
        "consistency": consistency, "hierarchy": hierarchy,
        "data_sources": data_sources,
    }


# ══════════════════════════════════════════════════════════════
# BSCL / HoNOSCA-SR Reporting
# ══════════════════════════════════════════════════════════════

BSCL_SHORT = {
    "soma": "Somatisierung", "zwan": "Zwanghaftigkeit", "unsi": "Unsicherheit",
    "depr": "Depressivität", "angs": "Ängstlichkeit", "aggr": "Aggressivität",
    "phob": "Phobische Angst", "para": "Paranoid", "psyc": "Psychotizismus",
}

# Offizielle BSCL-53 Item-Labels (Franke 2000/2016, dt. Fassung nach Derogatis)
BSCL_ITEM_LABELS = {
    1:  "Nervosität oder innerem Zittern",
    2:  "Ohnmachts- oder Schwindelgefühlen",
    3:  "der Idee, dass irgend jemand Macht über Ihre Gedanken hat",
    4:  "dem Gefühl, dass andere an den meisten Ihrer Schwierigkeiten Schuld sind",
    5:  "Gedächtnisschwierigkeiten",
    6:  "dem Gefühl, leicht reizbar oder verärgerbar zu sein",
    7:  "Herz- oder Brustschmerzen",
    8:  "Furcht auf offenen Plätzen oder auf der Strasse",
    9:  "Gedanken, sich das Leben zu nehmen",
    10: "dem Gefühl, dass man den meisten Menschen nicht trauen kann",
    11: "schlechtem Appetit",
    12: "plötzlichem Erschrecken ohne Grund",
    13: "Gefühlsausbrüchen, denen gegenüber Sie machtlos waren",
    14: "Einsamkeitsgefühlen, selbst wenn Sie in Gesellschaft sind",
    15: "dem Gefühl, dass es Ihnen schwer fällt, etwas anzufangen",
    16: "Einsamkeitsgefühlen",
    17: "Schwermut",
    18: "dem Gefühl, sich für nichts zu interessieren",
    19: "Furchtsamkeit",
    20: "Verletzlichkeit in Gefühlsdingen",
    21: "dem Gefühl, dass die Leute unfreundlich sind oder Sie nicht leiden können",
    22: "Minderwertigkeitsgefühlen gegenüber anderen",
    23: "Übelkeit oder Magenverstimmung",
    24: "dem Gefühl, dass andere Sie beobachten oder über Sie reden",
    25: "Einschlafschwierigkeiten",
    26: "dem Zwang, wieder und wieder nachzukontrollieren, was Sie tun",
    27: "Schwierigkeiten, sich zu entscheiden",
    28: "Furcht vor Fahrten in Bus, Strassenbahn, U-Bahn oder Zug",
    29: "Schwierigkeiten beim Atmen",
    30: "Hitzewallungen oder Kälteschauern",
    31: "der Notwendigkeit, bestimmte Dinge, Orte oder Tätigkeiten zu meiden",
    32: "Leere im Kopf",
    33: "Taubheit oder Kribbeln in einzelnen Körperteilen",
    34: "dem Gefühl, dass Sie für Ihre Sünden bestraft werden sollten",
    35: "einem Gefühl der Hoffnungslosigkeit angesichts der Zukunft",
    36: "Konzentrationsschwierigkeiten",
    37: "Schwächegefühl in einzelnen Körperteilen",
    38: "dem Gefühl, angespannt oder aufgeregt zu sein",
    39: "Gedanken an den Tod oder ans Sterben",
    40: "dem Drang, jemanden zu schlagen, zu verletzen oder ihm Schmerz zuzufügen",
    41: "dem Drang, Dinge zu zerbrechen oder zu zerschmettern",
    42: "starker Befangenheit im Umgang mit anderen",
    43: "Furcht in Menschenmengen, z.B. beim Einkaufen oder im Kino",
    44: "dem Eindruck, sich einer anderen Person nie so richtig nahe fühlen zu können",
    45: "Schreck- oder Panikanfällen",
    46: "der Neigung, immer wieder in Erörterungen und Auseinandersetzungen zu geraten",
    47: "Nervosität, wenn Sie allein gelassen werden",
    48: "mangelnder Anerkennung Ihrer Leistungen durch andere",
    49: "so starker Ruhelosigkeit, dass Sie nicht stillsitzen können",
    50: "dem Gefühl, wertlos zu sein",
    51: "dem Gefühl, dass die Leute Sie ausnutzen, wenn Sie es zulassen würden",
    52: "Schuldgefühlen",
    53: "dem Gedanken, dass irgendetwas mit Ihrem Verstand nicht stimmt",
}

# Map: item_nr → scale_key (for grouping)
BSCL_ITEM_TO_SCALE = {}
for _sk, _sd in BSCL_SCALES.items():
    for _it in _sd["items"]:
        BSCL_ITEM_TO_SCALE[_it] = _sk
# Items 11,25,39,52 → "zusatz" (nur GSI)
for _z in [11, 25, 39, 52]:
    BSCL_ITEM_TO_SCALE[_z] = "zusatz"


def _calc_bscl_scales(items: list | None) -> dict:
    """Berechne 9 BSCL-Skalenmittelwerte + GSI aus 53 Items."""
    if not items or len(items) < 53:
        return {k: None for k in BSCL_SCALES}  | {"gsi": None, "pst": None}
    result = {}
    for key, info in BSCL_SCALES.items():
        vals = [items[i - 1] for i in info["items"] if items[i - 1] is not None]
        result[key] = round(sum(vals) / len(vals), 2) if vals else None
    all_vals = [v for v in items if v is not None]
    result["gsi"] = round(sum(all_vals) / len(all_vals), 2) if all_vals else None
    result["pst"] = sum(1 for v in all_vals if v > 0)
    return result


@router.get("/api/reporting/bscl")
def bscl_report(
    ctx: AuthContext = Depends(get_auth_context),
    clinic: Optional[str] = Query(None),
    center: Optional[str] = Query(None),
    station: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """BSCL (Erwachsene) + HoNOSCA-SR (KJPP) Selbstbeurteilungs-Reporting."""
    all_cases = get_all_cases_enriched()
    hierarchy = _build_hierarchy()

    cases = []
    for c in all_cases:
        if clinic and c.get("clinic") != clinic: continue
        if center and c.get("center") != center: continue
        if station and c.get("station_id") != station: continue
        if year:
            adm = c.get("admission_date")
            if adm:
                try:
                    if int(str(adm)[:4]) != year: continue
                except (ValueError, TypeError): continue
            else: continue
        cases.append(c)

    scatter, worse_list = [], []
    with_entry = with_both = improved = same = worse = 0
    diffs_gsi, entries_gsi, discharges_gsi = [], [], []
    # Per-scale aggregation
    scale_keys = list(BSCL_SCALES.keys())
    scale_e_agg = {k: [] for k in scale_keys}
    scale_d_agg = {k: [] for k in scale_keys}
    # Per-item aggregation (1-indexed)
    item_entry_agg = {i: [] for i in range(1, 54)}
    item_discharge_agg = {i: [] for i in range(1, 54)}
    clinic_data, station_data = {}, {}

    for c in cases:
        is_kjpp = c.get("clinic") == "KJPP"
        e_items = c.get("bscl_entry_items")
        d_items = c.get("bscl_discharge_items")
        entry_gsi = c.get("bscl_total_entry")   # GSI for BSCL, normalized for HoNOSCA-SR
        discharge_gsi = c.get("bscl_total_discharge")

        instrument = "HoNOSCA-SR" if is_kjpp else "BSCL"

        if entry_gsi is not None:
            with_entry += 1
            entries_gsi.append(entry_gsi)

        if entry_gsi is not None and discharge_gsi is not None:
            with_both += 1
            diff = round(entry_gsi - discharge_gsi, 2)
            diffs_gsi.append(diff)
            discharges_gsi.append(discharge_gsi)
            if diff > 0.05: improved += 1
            elif diff < -0.05: worse += 1
            else: same += 1

            # Scale means (only for BSCL, not HoNOSCA-SR)
            if not is_kjpp and e_items and len(e_items) >= 53:
                scales_e = _calc_bscl_scales(e_items)
                scales_d = _calc_bscl_scales(d_items)
                for k in scale_keys:
                    if scales_e.get(k) is not None: scale_e_agg[k].append(scales_e[k])
                    if scales_d.get(k) is not None: scale_d_agg[k].append(scales_d[k])
                # Per-item aggregation
                for idx in range(53):
                    item_nr = idx + 1
                    if e_items[idx] is not None:
                        item_entry_agg[item_nr].append(e_items[idx])
                    if d_items and idx < len(d_items) and d_items[idx] is not None:
                        item_discharge_agg[item_nr].append(d_items[idx])

            clin = c.get("clinic", "?")
            sid = c.get("station_id", "")
            ctr = c.get("center", "")

            if clin not in clinic_data:
                clinic_data[clin] = {"n": 0, "diffs": [], "improved": 0}
            clinic_data[clin]["n"] += 1
            clinic_data[clin]["diffs"].append(diff)
            if diff > 0.05: clinic_data[clin]["improved"] += 1

            if sid not in station_data:
                station_data[sid] = {"n": 0, "diffs": [], "improved": 0, "clinic": clin, "center": ctr}
            station_data[sid]["n"] += 1
            station_data[sid]["diffs"].append(diff)
            if diff > 0.05: station_data[sid]["improved"] += 1

            scatter.append({
                "case_id": c.get("case_id"), "entry": entry_gsi, "discharge": discharge_gsi,
                "diff": diff, "clinic": clin, "station": sid, "center": ctr,
                "instrument": instrument,
                "admission": str(c.get("admission_date", ""))[:10],
                "discharge_date": str(c.get("discharge_date", ""))[:10] if c.get("discharge_date") else None,
                "suicidality_discharge": c.get("bscl_discharge_suicidality"),
            })
            if diff < -0.05:
                worse_list.append({
                    "case_id": c.get("case_id"), "station": sid, "clinic": clin,
                    "center": ctr, "entry": entry_gsi, "discharge": discharge_gsi, "diff": diff,
                    "admission": str(c.get("admission_date", ""))[:10],
                    "discharge_date": str(c.get("discharge_date", ""))[:10] if c.get("discharge_date") else None,
                })

    total = len(cases)
    sd = lambda a, b: round(a / b, 2) if b else 0
    kpis = {
        "total": total, "with_entry": with_entry, "with_both": with_both,
        "improved": improved, "same": same, "worse": worse,
        "avg_diff": sd(sum(diffs_gsi), len(diffs_gsi)) if diffs_gsi else None,
        "avg_entry": sd(sum(entries_gsi), len(entries_gsi)) if entries_gsi else None,
        "avg_discharge": sd(sum(discharges_gsi), len(discharges_gsi)) if discharges_gsi else None,
        "entry_completion_pct": sd(100 * with_entry, total),
        "pair_completion_pct": sd(100 * with_both, total),
        "improved_pct": sd(100 * improved, with_both),
        "worse_pct": sd(100 * worse, with_both),
    }

    # BSCL scales
    subscales = {}
    for k in scale_keys:
        e, d = scale_e_agg[k], scale_d_agg[k]
        subscales[k] = {
            "label": BSCL_SCALES[k]["label"], "max": 4.0,
            "avg_entry": sd(sum(e), len(e)) if e else None,
            "avg_discharge": sd(sum(d), len(d)) if d else None,
            "avg_diff": round((sum(e)/len(e)) - (sum(d)/len(d)), 2) if e and d else None,
        }

    # Per-item detail grouped by scale
    items_by_scale = {}
    for item_nr in range(1, 54):
        scale_key = BSCL_ITEM_TO_SCALE.get(item_nr, "zusatz")
        e_vals = item_entry_agg[item_nr]
        d_vals = item_discharge_agg[item_nr]
        detail = {
            "item": item_nr,
            "label": BSCL_ITEM_LABELS.get(item_nr, f"Item {item_nr}"),
            "avg_entry": sd(sum(e_vals), len(e_vals)) if e_vals else None,
            "avg_discharge": sd(sum(d_vals), len(d_vals)) if d_vals else None,
            "avg_diff": round((sum(e_vals)/len(e_vals)) - (sum(d_vals)/len(d_vals)), 2) if e_vals and d_vals else None,
            "n": len(e_vals),
        }
        items_by_scale.setdefault(scale_key, []).append(detail)

    by_clinic = [{"clinic": c, "n": d["n"],
                   "avg_diff": sd(sum(d["diffs"]), len(d["diffs"])),
                   "improved_pct": sd(100 * d["improved"], d["n"])}
                  for c, d in sorted(clinic_data.items())]

    by_station = [{"station": s, "clinic": d["clinic"], "center": d["center"],
                    "n": d["n"], "avg_diff": sd(sum(d["diffs"]), len(d["diffs"])),
                    "improved_pct": sd(100 * d["improved"], d["n"])}
                   for s, d in sorted(station_data.items())]

    hist = {}
    for d in diffs_gsi:
        b = round(d, 1)
        hist[b] = hist.get(b, 0) + 1
    histogram = [{"diff": k, "count": v} for k, v in sorted(hist.items())]

    consistency = {
        "total_cases": total,
        "bscl_complete": with_entry,
        "completion_pct": sd(100 * with_entry, total),
        "has_items": any(c.get("bscl_entry_items") for c in cases),
        "adults_bscl": sum(1 for c in cases if c.get("clinic") != "KJPP" and c.get("bscl_total_entry") is not None),
        "kjpp_honosca_sr": sum(1 for c in cases if c.get("clinic") == "KJPP" and c.get("bscl_total_entry") is not None),
    }

    worse_list.sort(key=lambda x: x["diff"])

    return {
        "scatter": scatter, "kpis": kpis, "subscales": subscales,
        "items_by_scale": items_by_scale,
        "by_clinic": by_clinic, "by_station": by_station,
        "histogram": histogram, "worse_list": worse_list,
        "consistency": consistency, "hierarchy": hierarchy,
    }
