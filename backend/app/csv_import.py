"""
Datei: backend/app/csv_import.py

CSV/Excel Import-Funktionalität für Case-Daten.
Importiert Fälle aus CSV/XLSX in die case_data-Tabelle.

Sicherheit:
- Validierung aller Eingabedaten
- Limits für Dateigröße und Anzahl Datensätze
- Keine Ausführung von Code aus CSV-Dateien
"""

from __future__ import annotations

import io
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.models import Case

logger = logging.getLogger(__name__)


# ---- Column Mapping ----
# Maps possible CSV column names to our internal field names
COLUMN_ALIASES = {
    "case_id": ["case_id", "fall_id", "fallnummer", "fall_nr", "case"],
    "station_id": ["station_id", "station", "ward", "ward_id"],
    "patient_id": ["patient_id", "pat_id", "patient_nr"],
    "patient_initials": ["patient_initials", "initials", "initialen"],
    "clinic": ["clinic", "klinik"],
    "center": ["center", "zentrum"],
    "admission_date": ["admission_date", "eintritt", "eintrittsdatum", "aufnahme", "aufnahmedatum"],
    "discharge_date": ["discharge_date", "austritt", "austrittsdatum", "entlassung", "entlassungsdatum"],
    "honos_entry_total": ["honos_entry_total", "honos_eintritt", "honos_entry"],
    "honos_discharge_total": ["honos_discharge_total", "honos_austritt", "honos_discharge"],
    "honos_discharge_suicidality": ["honos_discharge_suicidality", "honos_suizid_austritt"],
    "bscl_total_entry": ["bscl_total_entry", "bscl_eintritt", "bscl_entry"],
    "bscl_total_discharge": ["bscl_total_discharge", "bscl_austritt", "bscl_discharge"],
    "bscl_discharge_suicidality": ["bscl_discharge_suicidality", "bscl_suizid_austritt"],
    "bfs_1": ["bfs_1", "bfs1"],
    "bfs_2": ["bfs_2", "bfs2"],
    "bfs_3": ["bfs_3", "bfs3"],
    # --- SpiGes Personendaten ---
    "zivilstand": ["zivilstand", "3.2.v01"],
    "aufenthaltsort_vor_eintritt": ["aufenthaltsort_vor_eintritt", "aufenthaltsort", "3.2.v02"],
    "beschaeftigung_teilzeit": ["beschaeftigung_teilzeit", "3.2.v03"],
    "beschaeftigung_vollzeit": ["beschaeftigung_vollzeit", "3.2.v04"],
    "beschaeftigung_arbeitslos": ["beschaeftigung_arbeitslos", "3.2.v05"],
    "beschaeftigung_haushalt": ["beschaeftigung_haushalt", "3.2.v06"],
    "beschaeftigung_ausbildung": ["beschaeftigung_ausbildung", "3.2.v07"],
    "beschaeftigung_reha": ["beschaeftigung_reha", "3.2.v08"],
    "beschaeftigung_iv": ["beschaeftigung_iv", "3.2.v09"],
    "schulbildung": ["schulbildung", "3.2.v10"],
    # --- SpiGes Eintrittsmerkmale ---
    "einweisende_instanz": ["einweisende_instanz", "3.3.v01"],
    "behandlungsgrund": ["behandlungsgrund", "3.3.v02"],
    # --- SpiGes Austrittsmerkmale ---
    "entscheid_austritt": ["entscheid_austritt", "3.5.v01"],
    "aufenthalt_nach_austritt": ["aufenthalt_nach_austritt", "3.5.v02"],
    "behandlung_nach_austritt": ["behandlung_nach_austritt", "3.5.v03"],
    "behandlungsbereich": ["behandlungsbereich", "3.5.v04"],
    # --- FU ---
    "is_voluntary": ["is_voluntary", "freiwillig", "freiwilligkeit"],
    "fu_bei_eintritt": ["fu_bei_eintritt", "fu_eintritt", "3.3.v03"],
    "fu_typ": ["fu_typ"],
    "fu_datum": ["fu_datum"],
    "fu_gueltig_bis": ["fu_gueltig_bis"],
    "fu_nummer": ["fu_nummer"],
    "fu_einweisende_instanz": ["fu_einweisende_instanz"],
}


class ImportResult(BaseModel):
    """Ergebnis eines Imports."""
    success: bool
    total_rows: int
    imported_rows: int
    skipped_rows: int
    failed_rows: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CSVImporter:
    """CSV/Excel Import-Handler."""

    def __init__(self, max_rows: int = 10000, max_file_size_mb: int = 50):
        self.max_rows = max_rows
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def import_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        db: Session,
        station_id: Optional[str] = None,
        overwrite: bool = False,
        imported_by: str = "system",
    ) -> ImportResult:
        """Importiert Cases aus Datei-Bytes (für Upload-Endpoint)."""

        if len(file_content) > self.max_file_size_bytes:
            return ImportResult(
                success=False, total_rows=0, imported_rows=0, skipped_rows=0, failed_rows=0,
                errors=[{"row": 0, "error": f"Datei zu groß: {len(file_content) / 1024 / 1024:.1f}MB"}],
            )

        try:
            file_obj = io.BytesIO(file_content)
            if filename.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_obj, engine="openpyxl" if filename.lower().endswith(".xlsx") else None)
            else:
                # Try different encodings
                for enc in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        file_obj.seek(0)
                        df = pd.read_csv(file_obj, encoding=enc, sep=None, engine="python")
                        break
                    except Exception:
                        continue
                else:
                    return ImportResult(
                        success=False, total_rows=0, imported_rows=0, skipped_rows=0, failed_rows=0,
                        errors=[{"row": 0, "error": "Datei konnte nicht gelesen werden (Encoding-Problem)"}],
                    )
        except Exception as e:
            return ImportResult(
                success=False, total_rows=0, imported_rows=0, skipped_rows=0, failed_rows=0,
                errors=[{"row": 0, "error": f"Datei konnte nicht gelesen werden: {str(e)}"}],
            )

        if len(df) > self.max_rows:
            return ImportResult(
                success=False, total_rows=len(df), imported_rows=0, skipped_rows=0, failed_rows=0,
                errors=[{"row": 0, "error": f"Zu viele Zeilen: {len(df)} (max: {self.max_rows})"}],
            )

        return self._process_dataframe(df, db, station_id, overwrite, imported_by)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalisiert Spaltennamen und mappt Aliase."""
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        rename_map = {}
        for target, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in df.columns and alias != target:
                    rename_map[alias] = target
                    break

        if rename_map:
            df = df.rename(columns=rename_map)

        return df

    def _process_dataframe(
        self,
        df: pd.DataFrame,
        db: Session,
        station_id: Optional[str],
        overwrite: bool,
        imported_by: str,
    ) -> ImportResult:
        """Verarbeitet einen DataFrame und importiert die Daten."""

        df = self._normalize_columns(df)

        result = ImportResult(
            success=True, total_rows=len(df), imported_rows=0, skipped_rows=0, failed_rows=0,
        )

        # Validate required columns
        if "case_id" not in df.columns:
            result.success = False
            result.errors.append({"row": 0, "error": "Spalte 'case_id' fehlt"})
            return result

        if "station_id" not in df.columns and not station_id:
            result.success = False
            result.errors.append({"row": 0, "error": "Spalte 'station_id' fehlt und keine Station angegeben"})
            return result

        now_iso = datetime.utcnow().isoformat()

        for idx, row in df.iterrows():
            try:
                row_dict = row.to_dict()

                # NaN → None
                for key, value in row_dict.items():
                    if pd.isna(value):
                        row_dict[key] = None

                cid = str(row_dict.get("case_id", "")).strip()
                if not cid:
                    result.failed_rows += 1
                    result.errors.append({"row": int(idx) + 2, "error": "case_id ist leer"})
                    continue

                sid = station_id or str(row_dict.get("station_id", "")).strip()
                if not sid:
                    result.failed_rows += 1
                    result.errors.append({"row": int(idx) + 2, "case_id": cid, "error": "station_id ist leer"})
                    continue

                # Parse dates
                admission_date = self._parse_date(row_dict.get("admission_date"))
                discharge_date = self._parse_date(row_dict.get("discharge_date"))

                if not admission_date:
                    result.failed_rows += 1
                    result.errors.append({"row": int(idx) + 2, "case_id": cid, "error": "admission_date fehlt oder ungültig"})
                    continue

                # Check if case exists
                existing = db.get(Case, cid)
                if existing and not overwrite:
                    result.skipped_rows += 1
                    result.warnings.append(f"Zeile {int(idx) + 2}: case_id '{cid}' existiert bereits (übersprungen)")
                    continue

                case = existing or Case(case_id=cid)
                case.station_id = sid
                case.patient_id = str(row_dict.get("patient_id", "")) or None
                case.patient_initials = str(row_dict.get("patient_initials", "")) or None
                case.clinic = str(row_dict.get("clinic", "")) or "EPP"
                case.center = str(row_dict.get("center", "")) or None
                case.admission_date = admission_date
                case.discharge_date = discharge_date

                case.honos_entry_total = self._safe_int(row_dict.get("honos_entry_total"))
                case.honos_entry_date = self._parse_date(row_dict.get("honos_entry_date"))
                case.honos_discharge_total = self._safe_int(row_dict.get("honos_discharge_total"))
                case.honos_discharge_date = self._parse_date(row_dict.get("honos_discharge_date"))
                case.honos_discharge_suicidality = self._safe_int(row_dict.get("honos_discharge_suicidality"))

                case.bscl_total_entry = self._safe_int(row_dict.get("bscl_total_entry"))
                case.bscl_entry_date = self._parse_date(row_dict.get("bscl_entry_date"))
                case.bscl_total_discharge = self._safe_int(row_dict.get("bscl_total_discharge"))
                case.bscl_discharge_date = self._parse_date(row_dict.get("bscl_discharge_date"))
                case.bscl_discharge_suicidality = self._safe_int(row_dict.get("bscl_discharge_suicidality"))

                case.bfs_1 = str(row_dict.get("bfs_1")) if row_dict.get("bfs_1") is not None else None
                case.bfs_2 = str(row_dict.get("bfs_2")) if row_dict.get("bfs_2") is not None else None
                case.bfs_3 = str(row_dict.get("bfs_3")) if row_dict.get("bfs_3") is not None else None

                # --- SpiGes Personendaten ---
                case.zivilstand = str(row_dict.get("zivilstand")) if row_dict.get("zivilstand") is not None else None
                case.aufenthaltsort_vor_eintritt = str(row_dict.get("aufenthaltsort_vor_eintritt")) if row_dict.get("aufenthaltsort_vor_eintritt") is not None else None
                case.beschaeftigung_teilzeit = self._safe_int(row_dict.get("beschaeftigung_teilzeit"))
                case.beschaeftigung_vollzeit = self._safe_int(row_dict.get("beschaeftigung_vollzeit"))
                case.beschaeftigung_arbeitslos = self._safe_int(row_dict.get("beschaeftigung_arbeitslos"))
                case.beschaeftigung_haushalt = self._safe_int(row_dict.get("beschaeftigung_haushalt"))
                case.beschaeftigung_ausbildung = self._safe_int(row_dict.get("beschaeftigung_ausbildung"))
                case.beschaeftigung_reha = self._safe_int(row_dict.get("beschaeftigung_reha"))
                case.beschaeftigung_iv = self._safe_int(row_dict.get("beschaeftigung_iv"))
                case.schulbildung = str(row_dict.get("schulbildung")) if row_dict.get("schulbildung") is not None else None

                # --- SpiGes Eintrittsmerkmale ---
                case.einweisende_instanz = str(row_dict.get("einweisende_instanz")) if row_dict.get("einweisende_instanz") is not None else None
                case.behandlungsgrund = str(row_dict.get("behandlungsgrund")) if row_dict.get("behandlungsgrund") is not None else None

                # --- SpiGes Austrittsmerkmale ---
                case.entscheid_austritt = str(row_dict.get("entscheid_austritt")) if row_dict.get("entscheid_austritt") is not None else None
                case.aufenthalt_nach_austritt = str(row_dict.get("aufenthalt_nach_austritt")) if row_dict.get("aufenthalt_nach_austritt") is not None else None
                case.behandlung_nach_austritt = str(row_dict.get("behandlung_nach_austritt")) if row_dict.get("behandlung_nach_austritt") is not None else None
                case.behandlungsbereich = str(row_dict.get("behandlungsbereich")) if row_dict.get("behandlungsbereich") is not None else None

                # --- FU ---
                vol = row_dict.get("is_voluntary")
                if vol is not None:
                    case.is_voluntary = str(vol).strip().lower() in ("true", "1", "ja", "yes")
                case.fu_bei_eintritt = self._safe_int(row_dict.get("fu_bei_eintritt"))
                case.fu_typ = str(row_dict.get("fu_typ")) if row_dict.get("fu_typ") is not None else None
                case.fu_datum = self._parse_date(row_dict.get("fu_datum"))
                case.fu_gueltig_bis = self._parse_date(row_dict.get("fu_gueltig_bis"))
                case.fu_nummer = self._safe_int(row_dict.get("fu_nummer"))
                case.fu_einweisende_instanz = str(row_dict.get("fu_einweisende_instanz")) if row_dict.get("fu_einweisende_instanz") is not None else None

                case.isolations_json = None  # CSV hat normalerweise keine Isolation-Daten

                case.imported_at = now_iso
                case.imported_by = imported_by
                case.source = "csv"

                db.merge(case)
                result.imported_rows += 1

            except Exception as e:
                result.failed_rows += 1
                result.errors.append({
                    "row": int(idx) + 2,
                    "case_id": row.get("case_id", "UNKNOWN"),
                    "error": str(e),
                })
                logger.warning(f"Fehler beim Import von Zeile {idx + 2}: {e}")

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            result.success = False
            result.errors.append({"row": 0, "error": f"DB-Commit fehlgeschlagen: {str(e)}"})
            return result

        result.success = result.failed_rows == 0

        if result.failed_rows > 0:
            result.warnings.append(
                f"{result.failed_rows} von {result.total_rows} Zeilen konnten nicht importiert werden"
            )
        if result.skipped_rows > 0:
            result.warnings.append(
                f"{result.skipped_rows} Zeilen übersprungen (existieren bereits)"
            )

        return result

    @staticmethod
    def _parse_date(val) -> Optional[str]:
        """Parst ein Datum aus verschiedenen Formaten → ISO-String oder None."""
        if val is None:
            return None
        if isinstance(val, date):
            return val.isoformat()
        if isinstance(val, datetime):
            return val.date().isoformat()

        s = str(val).strip()
        if not s or s.lower() in ("nan", "nat", "none", "null", ""):
            return None

        # Try common formats
        for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                continue

        # Try pandas
        try:
            return pd.to_datetime(s).date().isoformat()
        except Exception:
            return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        """Konvertiert sicher zu int oder None."""
        if val is None:
            return None
        try:
            f = float(val)
            if pd.isna(f):
                return None
            return int(f)
        except (ValueError, TypeError):
            return None


def generate_sample_csv() -> str:
    """Generiert eine Beispiel-CSV als String."""
    import random

    headers = [
        "case_id", "station_id", "patient_id", "patient_initials", "clinic",
        "admission_date", "discharge_date",
        "honos_entry_total", "honos_discharge_total", "honos_discharge_suicidality",
        "bscl_total_entry", "bscl_total_discharge", "bscl_discharge_suicidality",
        "bfs_1", "bfs_2", "bfs_3",
    ]

    rows = [",".join(headers)]
    stations = ["A1", "B0", "B2", "ST01", "ST02"]

    for i in range(20):
        sid = random.choice(stations)
        adm = date(2026, 1, random.randint(1, 31) if random.randint(1, 31) <= 28 else 28)
        dis = ""
        if random.random() > 0.3:
            dis = date(2026, 2, random.randint(1, 13)).isoformat()

        row = [
            f"CASE_{i+1:04d}", sid, f"PAT_{i+1:04d}",
            f"{chr(65 + i % 26)}{chr(75 + i % 26)}", "EPP",
            adm.isoformat(), dis,
            str(random.randint(5, 40)) if random.random() > 0.2 else "",
            str(random.randint(5, 40)) if dis and random.random() > 0.3 else "",
            str(random.randint(0, 4)) if dis and random.random() > 0.5 else "",
            str(random.randint(10, 80)) if random.random() > 0.2 else "",
            str(random.randint(10, 80)) if dis and random.random() > 0.3 else "",
            str(random.randint(0, 4)) if dis and random.random() > 0.5 else "",
            str(random.randint(1, 15)) if random.random() > 0.1 else "",
            str(random.randint(1, 15)) if random.random() > 0.1 else "",
            str(random.randint(1, 15)) if random.random() > 0.1 else "",
        ]
        rows.append(",".join(row))

    return "\n".join(rows)
