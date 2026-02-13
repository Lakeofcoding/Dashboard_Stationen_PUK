"""
Datei: backend/app/db_enhanced.py

Zweck:
- Erweiterte Datenbank-Konfiguration
- PostgreSQL und SQLite Support
- Connection Pooling
- Performance-Optimierungen

Sicherheit:
- Connection Limits
- Timeout-Konfiguration
- SSL für PostgreSQL
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from app.logging_config import get_logger

logger = get_logger(__name__)


def get_database_url() -> str:
    """
    Holt die Datenbank-URL aus Umgebungsvariablen.
    
    Standard: SQLite (für Entwicklung/kleine Installationen)
    Produktion: PostgreSQL empfohlen
    """
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./data/app.db')
    
    # Relative SQLite-Pfade absolut machen
    if db_url.startswith('sqlite:///') and not db_url.startswith('sqlite:////'):
        db_path = db_url.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
            db_url = f'sqlite:///{db_path}'
    
    return db_url


def create_db_engine(database_url: str | None = None) -> Engine:
    """
    Erstellt eine Datenbank-Engine mit optimalen Einstellungen.
    
    Args:
        database_url: Optional: Datenbank-URL (sonst aus Umgebungsvariable)
        
    Returns:
        SQLAlchemy Engine
    """
    if database_url is None:
        database_url = get_database_url()
    
    logger.info(f"Erstelle Datenbank-Engine für: {database_url.split('@')[-1]}")
    
    # Engine-Konfiguration abhängig vom Datenbank-Typ
    if database_url.startswith('sqlite'):
        # SQLite: Keine Connection Pooling, WAL-Mode aktivieren
        engine = create_engine(
            database_url,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,  # 30 Sekunden Timeout
            },
            poolclass=NullPool,  # Kein Pooling für SQLite
            echo=os.getenv('DASHBOARD_DEBUG', '0') == '1'
        )
        
        # SQLite-spezifische Optimierungen
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """Aktiviert WAL-Mode und andere Optimierungen für SQLite."""
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=268435456")  # 256 MB
            cursor.execute("PRAGMA page_size=4096")
            cursor.execute("PRAGMA cache_size=-64000")  # 64 MB
            cursor.close()
            
    elif database_url.startswith('postgresql'):
        # PostgreSQL: Connection Pooling aktivieren
        pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
        max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '20'))
        pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '3600'))
        
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Teste Connection vor Verwendung
            echo=os.getenv('DASHBOARD_DEBUG', '0') == '1'
        )
        
        logger.info(
            f"PostgreSQL Pool konfiguriert: size={pool_size}, "
            f"max_overflow={max_overflow}, timeout={pool_timeout}s"
        )
    else:
        # Andere Datenbanken: Standard-Konfiguration
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_pre_ping=True,
            echo=os.getenv('DASHBOARD_DEBUG', '0') == '1'
        )
    
    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    """
    Erstellt eine Session-Factory.
    
    Args:
        engine: SQLAlchemy Engine
        
    Returns:
        Session-Factory
    """
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False  # Performance-Optimierung
    )


@contextmanager
def get_db_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """
    Context Manager für Datenbank-Sessions.
    
    Usage:
        with get_db_session() as db:
            # Datenbankoperationen
            ...
    
    Args:
        engine: Optional: Spezifische Engine (sonst Default)
        
    Yields:
        Datenbank-Session
    """
    if engine is None:
        from app.db import engine as default_engine
        engine = default_engine
    
    session_factory = create_session_factory(engine)
    session = session_factory()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection(engine: Engine) -> bool:
    """
    Prüft, ob die Datenbankverbindung funktioniert.
    
    Args:
        engine: SQLAlchemy Engine
        
    Returns:
        True wenn Verbindung OK, sonst False
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Datenbankverbindung erfolgreich getestet")
        return True
    except Exception as e:
        logger.error(f"Datenbankverbindung fehlgeschlagen: {e}")
        return False


def optimize_database(engine: Engine) -> None:
    """
    Führt Datenbank-Optimierungen durch (VACUUM, ANALYZE, etc.).
    
    Args:
        engine: SQLAlchemy Engine
    """
    database_url = str(engine.url)
    
    try:
        with engine.connect() as conn:
            if database_url.startswith('sqlite'):
                logger.info("Führe SQLite-Optimierung durch...")
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                logger.info("SQLite-Optimierung abgeschlossen")
                
            elif database_url.startswith('postgresql'):
                logger.info("Führe PostgreSQL-Optimierung durch...")
                # VACUUM kann nicht in Transaction laufen
                conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute("VACUUM ANALYZE")
                logger.info("PostgreSQL-Optimierung abgeschlossen")
                
    except Exception as e:
        logger.error(f"Fehler bei Datenbank-Optimierung: {e}")


def get_database_info(engine: Engine) -> dict:
    """
    Holt Informationen über die Datenbank.
    
    Args:
        engine: SQLAlchemy Engine
        
    Returns:
        Dictionary mit Datenbank-Informationen
    """
    info = {
        'type': engine.dialect.name,
        'driver': engine.driver,
        'url': str(engine.url).split('@')[-1],  # Ohne Credentials
    }
    
    try:
        with engine.connect() as conn:
            if engine.dialect.name == 'sqlite':
                result = conn.execute("PRAGMA journal_mode")
                info['journal_mode'] = result.scalar()
                
                result = conn.execute("PRAGMA page_count")
                page_count = result.scalar()
                result = conn.execute("PRAGMA page_size")
                page_size = result.scalar()
                info['database_size_mb'] = (page_count * page_size) / (1024 * 1024)
                
            elif engine.dialect.name == 'postgresql':
                result = conn.execute("SELECT version()")
                info['version'] = result.scalar()
                
                result = conn.execute(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )
                info['database_size'] = result.scalar()
    except Exception as e:
        logger.warning(f"Konnte Datenbank-Info nicht abrufen: {e}")
    
    return info
