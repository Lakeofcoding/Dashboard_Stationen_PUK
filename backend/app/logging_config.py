"""
Datei: backend/app/logging_config.py

Zweck:
- Strukturiertes Logging für bessere Nachvollziehbarkeit
- Separate Log-Streams für verschiedene Zwecke
- DSGVO-konformes Logging (keine Patientendaten in Logs)

Sicherheit:
- Automatisches Filtern sensibler Daten
- Separate Audit-Logs
- Log-Rotation
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict

import structlog


# Sensible Felder, die nie geloggt werden sollen
SENSITIVE_FIELDS = {
    'password',
    'token',
    'secret',
    'api_key',
    'patient_name',
    'patient_id',
    'birthdate',
    'ssn',
    'insurance_number'
}


def filter_sensitive_data(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Filtert sensible Daten aus Log-Events."""
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            event_dict[key] = '***FILTERED***'
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path | str = "logs",
    enable_json: bool = False
) -> None:
    """
    Konfiguriert das Logging-System.
    
    Args:
        log_level: Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Verzeichnis für Log-Dateien
        enable_json: Falls True, wird JSON-Format verwendet (besser für maschinelle Verarbeitung)
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Standard Python Logging konfigurieren
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # Console Handler
            logging.StreamHandler(sys.stdout),
            # File Handler mit Rotation
            logging.handlers.RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=10,
                encoding='utf-8'
            )
        ]
    )
    
    # Structlog konfigurieren
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        filter_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Separate Audit-Log-Datei
    audit_handler = logging.handlers.RotatingFileHandler(
        log_dir / "audit.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=50,  # Audit-Logs länger aufbewahren
        encoding='utf-8'
    )
    audit_handler.setFormatter(
        logging.Formatter('%(asctime)s - AUDIT - %(message)s')
    )
    
    audit_logger = logging.getLogger('audit')
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Nicht an Root-Logger weiterleiten
    
    # Security-Log-Datei
    security_handler = logging.handlers.RotatingFileHandler(
        log_dir / "security.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=50,
        encoding='utf-8'
    )
    security_handler.setFormatter(
        logging.Formatter('%(asctime)s - SECURITY - %(message)s')
    )
    
    security_logger = logging.getLogger('security')
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.WARNING)
    security_logger.propagate = False


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Gibt einen konfigurierten Logger zurück.
    
    Args:
        name: Name des Loggers (üblicherweise __name__)
        
    Returns:
        Konfigurierter Structlog-Logger
    """
    return structlog.get_logger(name)


def audit_log(action: str, user_id: str, details: Dict[str, Any] | None = None):
    """
    Schreibt einen Audit-Log-Eintrag.
    
    Args:
        action: Durchgeführte Aktion
        user_id: Benutzer-ID (anonymisiert)
        details: Zusätzliche Details (werden gefiltert)
    """
    audit_logger = logging.getLogger('audit')
    
    details = details or {}
    filtered_details = filter_sensitive_data(details.copy())
    
    audit_logger.info(
        f"action={action} user={user_id} details={filtered_details}"
    )


def security_log(
    event: str,
    severity: str,
    user_id: str | None = None,
    ip: str | None = None,
    details: Dict[str, Any] | None = None
):
    """
    Schreibt einen Security-Log-Eintrag.
    
    Args:
        event: Security-Event
        severity: INFO, WARNING, ERROR, CRITICAL
        user_id: Benutzer-ID (falls verfügbar)
        ip: IP-Adresse (falls verfügbar)
        details: Zusätzliche Details
    """
    security_logger = logging.getLogger('security')
    
    details = details or {}
    filtered_details = filter_sensitive_data(details.copy())
    
    log_msg = f"event={event} user={user_id or 'UNKNOWN'} ip={ip or 'UNKNOWN'} details={filtered_details}"
    
    level = getattr(logging, severity.upper(), logging.WARNING)
    security_logger.log(level, log_msg)
