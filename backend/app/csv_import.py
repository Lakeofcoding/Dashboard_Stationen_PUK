"""
Datei: backend/app/csv_import.py

Zweck:
- CSV/Excel Import-Funktionalität für Dummy-Daten und spätere Datenimporte
- Validierung und Transformation von Case-Daten
- Bulk-Import mit Fehlerbehandlung

Sicherheit:
- Validierung aller Eingabedaten
- Limits für Dateigröße und Anzahl Datensätze
- Keine Ausführung von Code aus CSV-Dateien
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from decimal import Decimal

import pandas as pd
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CaseImportRow(BaseModel):
    """Validierungsmodell für eine importierte Fall-Zeile."""
    
    case_id: str = Field(..., min_length=1, max_length=50)
    station_id: str = Field(..., min_length=1, max_length=20)
    
    # Stammdaten
    patient_initials: Optional[str] = Field(None, max_length=10)
    admission_date: date
    discharge_date: Optional[date] = None
    
    # HONOS Scores
    honos_entry_total: Optional[int] = Field(None, ge=0, le=48)
    honos_discharge_total: Optional[int] = Field(None, ge=0, le=48)
    honos_entry_suicidality: Optional[int] = Field(None, ge=0, le=4)
    honos_discharge_suicidality: Optional[int] = Field(None, ge=0, le=4)
    
    # BSCL Scores
    bscl_total_entry: Optional[float] = Field(None, ge=0.0, le=4.0)
    bscl_total_discharge: Optional[float] = Field(None, ge=0.0, le=4.0)
    bscl_entry_suicidality: Optional[float] = Field(None, ge=0.0, le=4.0)
    bscl_discharge_suicidality: Optional[float] = Field(None, ge=0.0, le=4.0)
    
    # BFS Daten
    bfs_1: Optional[str] = Field(None, max_length=50)
    bfs_2: Optional[str] = Field(None, max_length=50)
    bfs_3: Optional[str] = Field(None, max_length=50)
    
    # Isolation
    isolation_start: Optional[datetime] = None
    isolation_end: Optional[datetime] = None
    
    @validator('discharge_date')
    def validate_discharge(cls, v, values):
        """Austritt darf nicht vor Eintritt liegen."""
        if v and 'admission_date' in values:
            if v < values['admission_date']:
                raise ValueError('Austrittsdatum darf nicht vor Eintrittsdatum liegen')
        return v
    
    @validator('isolation_end')
    def validate_isolation(cls, v, values):
        """Isolation Ende darf nicht vor Start liegen."""
        if v and 'isolation_start' in values and values['isolation_start']:
            if v < values['isolation_start']:
                raise ValueError('Isolation Ende darf nicht vor Start liegen')
        return v


class ImportResult(BaseModel):
    """Ergebnis eines Imports."""
    
    success: bool
    total_rows: int
    imported_rows: int
    failed_rows: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CSVImporter:
    """CSV/Excel Import-Handler."""
    
    def __init__(self, max_rows: int = 10000, max_file_size_mb: int = 50):
        self.max_rows = max_rows
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
    
    def import_from_file(
        self,
        file_path: Path | str,
        db: Session,
        station_id: Optional[str] = None,
        overwrite: bool = False
    ) -> ImportResult:
        """
        Importiert Cases aus einer CSV- oder Excel-Datei.
        
        Args:
            file_path: Pfad zur Datei
            db: Datenbank-Session
            station_id: Optional: Station-ID für alle importierten Cases
            overwrite: Falls True, werden existierende Cases überschrieben
            
        Returns:
            ImportResult mit Details zum Import
        """
        file_path = Path(file_path)
        
        # Dateigrößen-Check
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size_bytes:
            return ImportResult(
                success=False,
                total_rows=0,
                imported_rows=0,
                failed_rows=0,
                errors=[{
                    'row': 0,
                    'error': f'Datei zu groß: {file_size / 1024 / 1024:.1f}MB (max: {self.max_file_size_bytes / 1024 / 1024}MB)'
                }]
            )
        
        # Datei einlesen
        try:
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, engine='openpyxl' if file_path.suffix.lower() == '.xlsx' else None)
            else:
                df = pd.read_csv(file_path, encoding='utf-8')
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Datei: {e}")
            return ImportResult(
                success=False,
                total_rows=0,
                imported_rows=0,
                failed_rows=0,
                errors=[{'row': 0, 'error': f'Datei konnte nicht gelesen werden: {str(e)}'}]
            )
        
        # Anzahl Zeilen prüfen
        if len(df) > self.max_rows:
            return ImportResult(
                success=False,
                total_rows=len(df),
                imported_rows=0,
                failed_rows=0,
                errors=[{
                    'row': 0,
                    'error': f'Zu viele Zeilen: {len(df)} (max: {self.max_rows})'
                }]
            )
        
        # Import durchführen
        return self._process_dataframe(df, db, station_id, overwrite)
    
    def import_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        db: Session,
        station_id: Optional[str] = None,
        overwrite: bool = False
    ) -> ImportResult:
        """
        Importiert Cases aus Datei-Bytes (für Upload-Endpoint).
        
        Args:
            file_content: Datei-Inhalt als Bytes
            filename: Dateiname (für Format-Erkennung)
            db: Datenbank-Session
            station_id: Optional: Station-ID für alle importierten Cases
            overwrite: Falls True, werden existierende Cases überschrieben
            
        Returns:
            ImportResult mit Details zum Import
        """
        # Größen-Check
        if len(file_content) > self.max_file_size_bytes:
            return ImportResult(
                success=False,
                total_rows=0,
                imported_rows=0,
                failed_rows=0,
                errors=[{
                    'row': 0,
                    'error': f'Datei zu groß: {len(file_content) / 1024 / 1024:.1f}MB'
                }]
            )
        
        # Datei einlesen
        try:
            file_obj = io.BytesIO(file_content)
            if filename.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_obj, engine='openpyxl' if filename.lower().endswith('.xlsx') else None)
            else:
                df = pd.read_csv(file_obj, encoding='utf-8')
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Datei: {e}")
            return ImportResult(
                success=False,
                total_rows=0,
                imported_rows=0,
                failed_rows=0,
                errors=[{'row': 0, 'error': f'Datei konnte nicht gelesen werden: {str(e)}'}]
            )
        
        return self._process_dataframe(df, db, station_id, overwrite)
    
    def _process_dataframe(
        self,
        df: pd.DataFrame,
        db: Session,
        station_id: Optional[str],
        overwrite: bool
    ) -> ImportResult:
        """Verarbeitet einen DataFrame und importiert die Daten."""
        
        result = ImportResult(
            success=True,
            total_rows=len(df),
            imported_rows=0,
            failed_rows=0
        )
        
        # Spalten normalisieren (Leerzeichen entfernen, lowercase)
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Zeile für Zeile verarbeiten
        for idx, row in df.iterrows():
            try:
                # Station-ID überschreiben falls angegeben
                row_dict = row.to_dict()
                if station_id:
                    row_dict['station_id'] = station_id
                
                # NaN zu None konvertieren
                for key, value in row_dict.items():
                    if pd.isna(value):
                        row_dict[key] = None
                
                # Validieren
                case_row = CaseImportRow(**row_dict)
                
                # In Datenbank speichern (hier müsste die tatsächliche DB-Logik hin)
                # Dies ist ein Platzhalter - in der echten Implementation würde hier
                # der Case in die Datenbank geschrieben werden
                self._save_case_to_db(case_row, db, overwrite)
                
                result.imported_rows += 1
                
            except Exception as e:
                result.failed_rows += 1
                result.errors.append({
                    'row': int(idx) + 2,  # +2 wegen Header und 0-basiertem Index
                    'case_id': row.get('case_id', 'UNKNOWN'),
                    'error': str(e)
                })
                logger.warning(f"Fehler beim Import von Zeile {idx + 2}: {e}")
        
        result.success = result.failed_rows == 0
        
        if result.failed_rows > 0:
            result.warnings.append(
                f"{result.failed_rows} von {result.total_rows} Zeilen konnten nicht importiert werden"
            )
        
        return result
    
    def _save_case_to_db(self, case_row: CaseImportRow, db: Session, overwrite: bool):
        """
        Speichert einen Case in der Datenbank.
        
        TODO: Diese Methode muss noch mit der tatsächlichen Case-Datenstruktur
        aus dem Hauptprojekt verbunden werden.
        """
        # Platzhalter - hier würde die echte DB-Logik implementiert
        pass


def generate_sample_csv(output_path: Path, num_rows: int = 100) -> Path:
    """
    Generiert eine Beispiel-CSV mit Dummy-Daten für Tests.
    
    Args:
        output_path: Ausgabepfad
        num_rows: Anzahl zu generierender Zeilen
        
    Returns:
        Pfad zur erstellten Datei
    """
    from faker import Faker
    import random
    
    fake = Faker('de_CH')
    
    data = []
    stations = ['ST01', 'ST02', 'ST03', 'A1', 'A2', 'B1']
    
    for i in range(num_rows):
        admission = fake.date_between(start_date='-90d', end_date='today')
        discharge = None
        if random.random() > 0.3:  # 70% haben Austritt
            discharge = fake.date_between(start_date=admission, end_date='today')
        
        # Scores
        honos_entry = random.randint(0, 48) if random.random() > 0.1 else None
        honos_discharge = random.randint(0, 48) if discharge and random.random() > 0.2 else None
        
        bscl_entry = round(random.uniform(0, 4), 2) if random.random() > 0.1 else None
        bscl_discharge = round(random.uniform(0, 4), 2) if discharge and random.random() > 0.2 else None
        
        row = {
            'case_id': f'CASE_{i+1:05d}',
            'station_id': random.choice(stations),
            'patient_initials': f"{fake.first_name()[0]}{fake.last_name()[0]}",
            'admission_date': admission.isoformat(),
            'discharge_date': discharge.isoformat() if discharge else None,
            'honos_entry_total': honos_entry,
            'honos_discharge_total': honos_discharge,
            'honos_entry_suicidality': random.randint(0, 4) if honos_entry else None,
            'honos_discharge_suicidality': random.randint(0, 4) if honos_discharge else None,
            'bscl_total_entry': bscl_entry,
            'bscl_total_discharge': bscl_discharge,
            'bscl_entry_suicidality': round(random.uniform(0, 4), 2) if bscl_entry else None,
            'bscl_discharge_suicidality': round(random.uniform(0, 4), 2) if bscl_discharge else None,
            'bfs_1': random.choice(['V1', 'V2', 'V3', None]),
            'bfs_2': random.choice(['A', 'B', 'C', None]),
            'bfs_3': random.choice(['X', 'Y', 'Z', None]),
        }
        
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8')
    
    logger.info(f"Beispiel-CSV mit {num_rows} Zeilen erstellt: {output_path}")
    return output_path
