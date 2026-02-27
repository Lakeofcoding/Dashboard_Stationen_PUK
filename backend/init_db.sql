-- PUK Dashboard - PostgreSQL Initialisierung
-- Dieses Skript wird beim ersten Start des PostgreSQL-Containers ausgeführt.
-- Die eigentliche Schema-Erstellung erfolgt durch SQLAlchemy / init_db() beim Backend-Start.

-- Datenbankeinstellungen
ALTER DATABASE puk_dashboard SET timezone TO 'Europe/Zurich';
ALTER DATABASE puk_dashboard SET lc_messages TO 'en_US.UTF-8';

-- Extensions (optional, für spätere Volltext-Suche)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
