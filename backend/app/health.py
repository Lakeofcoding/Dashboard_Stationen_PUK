"""
Datei: backend/app/health.py

Zweck:
- Health-Check-Endpoints für Monitoring
- Bereitschafts- und Lebendigkeit-Checks
- Detaillierte System-Informationen

Verwendung:
- Kubernetes Readiness/Liveness Probes
- Monitoring-Systeme
- Load Balancer Health Checks
"""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import psutil
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db_enhanced import check_database_connection, get_database_info
from app.logging_config import get_logger

logger = get_logger(__name__)


class HealthStatus(BaseModel):
    """Health-Status-Modell."""
    
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    version: str
    uptime_seconds: float
    checks: Dict[str, Any]


class DetailedHealthStatus(HealthStatus):
    """Erweiterte Health-Informationen."""
    
    system: Dict[str, Any]
    database: Dict[str, Any]
    resources: Dict[str, Any]


# Startup-Zeit für Uptime-Berechnung
_STARTUP_TIME = datetime.now(timezone.utc)


def get_basic_health() -> HealthStatus:
    """
    Gibt einen einfachen Health-Status zurück.
    Schnell, für Load Balancer / Liveness Probes.
    
    Returns:
        HealthStatus
    """
    now = datetime.now(timezone.utc)
    uptime = (now - _STARTUP_TIME).total_seconds()
    
    return HealthStatus(
        status="healthy",
        timestamp=now,
        version=os.getenv('APP_VERSION', '1.0.0'),
        uptime_seconds=uptime,
        checks={
            'api': 'ok'
        }
    )


def get_detailed_health(db: Session, engine) -> DetailedHealthStatus:
    """
    Gibt detaillierte Health-Informationen zurück.
    Für Monitoring und Debugging.
    
    Args:
        db: Datenbank-Session
        engine: SQLAlchemy Engine
        
    Returns:
        DetailedHealthStatus
    """
    now = datetime.now(timezone.utc)
    uptime = (now - _STARTUP_TIME).total_seconds()
    
    checks = {
        'api': 'ok',
        'database': 'unknown',
        'disk': 'unknown',
        'memory': 'unknown'
    }
    
    overall_status = 'healthy'
    
    # Datenbank-Check
    try:
        db_ok = check_database_connection(engine)
        checks['database'] = 'ok' if db_ok else 'failed'
        if not db_ok:
            overall_status = 'unhealthy'
    except Exception as e:
        logger.error(f"Datenbank-Health-Check fehlgeschlagen: {e}")
        checks['database'] = 'failed'
        overall_status = 'unhealthy'
    
    # Disk-Space-Check
    try:
        data_dir = Path('data')
        if data_dir.exists():
            disk_usage = psutil.disk_usage(str(data_dir))
            disk_free_percent = (disk_usage.free / disk_usage.total) * 100
            
            if disk_free_percent < 5:
                checks['disk'] = 'critical'
                overall_status = 'unhealthy'
            elif disk_free_percent < 10:
                checks['disk'] = 'warning'
                if overall_status == 'healthy':
                    overall_status = 'degraded'
            else:
                checks['disk'] = 'ok'
        else:
            checks['disk'] = 'ok'
    except Exception as e:
        logger.warning(f"Disk-Check fehlgeschlagen: {e}")
        checks['disk'] = 'unknown'
    
    # Memory-Check
    try:
        memory = psutil.virtual_memory()
        if memory.percent > 95:
            checks['memory'] = 'critical'
            overall_status = 'unhealthy'
        elif memory.percent > 85:
            checks['memory'] = 'warning'
            if overall_status == 'healthy':
                overall_status = 'degraded'
        else:
            checks['memory'] = 'ok'
    except Exception as e:
        logger.warning(f"Memory-Check fehlgeschlagen: {e}")
        checks['memory'] = 'unknown'
    
    # System-Informationen
    system_info = {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'python_version': sys.version.split()[0],
        'hostname': platform.node(),
        'cpu_count': psutil.cpu_count(),
        'cpu_percent': psutil.cpu_percent(interval=1),
    }
    
    # Datenbank-Informationen
    try:
        db_info = get_database_info(engine)
    except Exception as e:
        logger.warning(f"Konnte DB-Info nicht abrufen: {e}")
        db_info = {'error': str(e)}
    
    # Ressourcen-Informationen
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        resources_info = {
            'memory': {
                'total_mb': memory.total / (1024 * 1024),
                'available_mb': memory.available / (1024 * 1024),
                'used_percent': memory.percent
            },
            'disk': {
                'total_gb': disk.total / (1024 * 1024 * 1024),
                'free_gb': disk.free / (1024 * 1024 * 1024),
                'used_percent': disk.percent
            }
        }
    except Exception as e:
        logger.warning(f"Konnte Ressourcen-Info nicht abrufen: {e}")
        resources_info = {'error': str(e)}
    
    return DetailedHealthStatus(
        status=overall_status,
        timestamp=now,
        version=os.getenv('APP_VERSION', '1.0.0'),
        uptime_seconds=uptime,
        checks=checks,
        system=system_info,
        database=db_info,
        resources=resources_info
    )


def is_ready(db: Session, engine) -> bool:
    """
    Prüft, ob die Anwendung bereit ist, Requests zu verarbeiten.
    Für Kubernetes Readiness Probes.
    
    Args:
        db: Datenbank-Session
        engine: SQLAlchemy Engine
        
    Returns:
        True wenn bereit, sonst False
    """
    try:
        # Datenbank muss erreichbar sein
        if not check_database_connection(engine):
            return False
        
        # Weitere Bereitschafts-Checks könnten hier hinzugefügt werden
        
        return True
    except Exception as e:
        logger.error(f"Readiness-Check fehlgeschlagen: {e}")
        return False


def is_alive() -> bool:
    """
    Prüft, ob die Anwendung noch läuft.
    Für Kubernetes Liveness Probes.
    
    Returns:
        True (wenn dieser Code ausgeführt wird, läuft die App noch)
    """
    return True
