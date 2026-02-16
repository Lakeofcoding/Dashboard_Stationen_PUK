#!/usr/bin/env bash
# =============================================================================
# Alembic Migration Helper
# =============================================================================
#
# Verwendung:
#   ./migrate.sh                  # Migrationen ausführen (upgrade head)
#   ./migrate.sh stamp            # Bestehende DB als "aktuell" markieren
#   ./migrate.sh new "beschreibung"  # Neue Migration erstellen (autogenerate)
#   ./migrate.sh history          # Migrations-Historie anzeigen
#   ./migrate.sh downgrade -1     # Letzte Migration rückgängig machen
#
# Voraussetzung: Ausführung im backend/ Verzeichnis
# =============================================================================

set -e
cd "$(dirname "$0")"

case "${1:-upgrade}" in
    upgrade)
        echo "▶ Migrationen ausführen…"
        python -m alembic upgrade head
        echo "✓ Datenbank ist aktuell."
        ;;
    stamp)
        echo "▶ Bestehende DB als aktuell markieren (stamp head)…"
        python -m alembic stamp head
        echo "✓ DB gestampt."
        ;;
    new|create)
        MSG="${2:-auto_migration}"
        echo "▶ Neue Migration erstellen: $MSG"
        python -m alembic revision --autogenerate -m "$MSG"
        echo "✓ Migration erstellt in alembic/versions/"
        ;;
    history)
        python -m alembic history --verbose
        ;;
    downgrade)
        TARGET="${2:--1}"
        echo "▶ Downgrade auf: $TARGET"
        python -m alembic downgrade "$TARGET"
        echo "✓ Downgrade abgeschlossen."
        ;;
    current)
        python -m alembic current
        ;;
    *)
        echo "Unbekannter Befehl: $1"
        echo "Nutzung: $0 [upgrade|stamp|new|history|downgrade|current]"
        exit 1
        ;;
esac
