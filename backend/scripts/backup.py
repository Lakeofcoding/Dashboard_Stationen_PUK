#!/usr/bin/env python3
"""
Datei: backend/scripts/backup.py

Zweck:
- Automatisches Backup der Datenbank
- Kompression und Verschlüsselung (optional)
- Retention-Management

Verwendung:
    python scripts/backup.py [--encrypt] [--retention-days 30]
"""

import argparse
import gzip
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Pfad anpassen für Imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db_enhanced import get_database_url
from app.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def create_backup(
    output_dir: Path,
    compress: bool = True,
    encrypt: bool = False,
    encryption_key: Optional[str] = None
) -> Path:
    """
    Erstellt ein Backup der Datenbank.
    
    Args:
        output_dir: Ausgabeverzeichnis
        compress: Falls True, wird das Backup komprimiert
        encrypt: Falls True, wird das Backup verschlüsselt
        encryption_key: Verschlüsselungs-Key (erforderlich falls encrypt=True)
        
    Returns:
        Pfad zur Backup-Datei
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    db_url = get_database_url()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if db_url.startswith('sqlite'):
        # SQLite: Datei kopieren
        db_path = db_url.replace('sqlite:///', '')
        source_path = Path(db_path)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Datenbank-Datei nicht gefunden: {source_path}")
        
        backup_name = f"backup_{timestamp}.db"
        backup_path = output_dir / backup_name
        
        logger.info(f"Erstelle SQLite-Backup: {source_path} -> {backup_path}")
        shutil.copy2(source_path, backup_path)
        
    elif db_url.startswith('postgresql'):
        # PostgreSQL: pg_dump verwenden
        import subprocess
        
        backup_name = f"backup_{timestamp}.sql"
        backup_path = output_dir / backup_name
        
        # Connection-Parameter aus URL extrahieren
        # Format: postgresql://user:pass@host:port/dbname
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        
        env = {
            'PGPASSWORD': parsed.password or ''
        }
        
        cmd = [
            'pg_dump',
            '-h', parsed.hostname or 'localhost',
            '-p', str(parsed.port or 5432),
            '-U', parsed.username or 'postgres',
            '-d', parsed.path.lstrip('/'),
            '-F', 'c',  # Custom format (besser als SQL)
            '-f', str(backup_path)
        ]
        
        logger.info(f"Erstelle PostgreSQL-Backup: {backup_path}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump fehlgeschlagen: {result.stderr}")
    else:
        raise ValueError(f"Nicht unterstützter Datenbank-Typ: {db_url}")
    
    # Kompression
    if compress:
        logger.info("Komprimiere Backup...")
        compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')
        
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        backup_path.unlink()  # Original löschen
        backup_path = compressed_path
    
    # Verschlüsselung (optional)
    if encrypt:
        if not encryption_key:
            raise ValueError("Encryption-Key erforderlich für verschlüsseltes Backup")
        
        logger.info("Verschlüssele Backup...")
        
        try:
            from cryptography.fernet import Fernet
            
            # Key muss Base64-encoded sein
            if len(encryption_key) != 44:
                # Key generieren falls nicht valid
                encryption_key = Fernet.generate_key().decode()
                logger.warning(f"Neuer Encryption-Key generiert: {encryption_key}")
            
            fernet = Fernet(encryption_key.encode())
            
            with open(backup_path, 'rb') as f:
                encrypted_data = fernet.encrypt(f.read())
            
            encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            backup_path.unlink()  # Unverschlüsselt löschen
            backup_path = encrypted_path
            
        except ImportError:
            logger.error("cryptography-Paket nicht installiert. Verschlüsselung übersprungen.")
    
    file_size_mb = backup_path.stat().st_size / (1024 * 1024)
    logger.info(f"Backup erstellt: {backup_path} ({file_size_mb:.2f} MB)")
    
    return backup_path


def cleanup_old_backups(backup_dir: Path, retention_days: int = 30):
    """
    Löscht alte Backups.
    
    Args:
        backup_dir: Backup-Verzeichnis
        retention_days: Anzahl Tage, die Backups aufbewahrt werden
    """
    if not backup_dir.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    
    logger.info(f"Lösche Backups älter als {retention_days} Tage...")
    
    for backup_file in backup_dir.glob('backup_*'):
        if backup_file.is_file():
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            
            if file_time < cutoff_date:
                logger.info(f"Lösche altes Backup: {backup_file}")
                backup_file.unlink()
                deleted_count += 1
    
    logger.info(f"{deleted_count} alte Backups gelöscht")


def main():
    """Haupt-Funktion für CLI."""
    parser = argparse.ArgumentParser(description='Erstellt ein Datenbank-Backup')
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('backups'),
        help='Ausgabeverzeichnis (default: backups/)'
    )
    parser.add_argument(
        '--compress',
        action='store_true',
        default=True,
        help='Backup komprimieren (default: True)'
    )
    parser.add_argument(
        '--encrypt',
        action='store_true',
        help='Backup verschlüsseln'
    )
    parser.add_argument(
        '--encryption-key',
        type=str,
        help='Verschlüsselungs-Key (Base64)'
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=30,
        help='Anzahl Tage für Backup-Aufbewahrung (default: 30)'
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Alte Backups nicht löschen'
    )
    
    args = parser.parse_args()
    
    try:
        # Backup erstellen
        backup_path = create_backup(
            output_dir=args.output_dir,
            compress=args.compress,
            encrypt=args.encrypt,
            encryption_key=args.encryption_key
        )
        
        # Alte Backups löschen
        if not args.no_cleanup:
            cleanup_old_backups(args.output_dir, args.retention_days)
        
        print(f"✓ Backup erfolgreich: {backup_path}")
        return 0
        
    except Exception as e:
        logger.error(f"Backup fehlgeschlagen: {e}", exc_info=True)
        print(f"✗ Fehler: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
