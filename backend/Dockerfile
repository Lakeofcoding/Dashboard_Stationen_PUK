# Dockerfile für PUK Dashboard Backend
# Optimiert für Offline-Betrieb in klinischer Umgebung

FROM python:3.11-slim

# Metadata
LABEL maintainer="PUK Dashboard Team"
LABEL description="Dashboard Backend für psychiatrische Stationen - Offline-fähig"
LABEL version="1.0.0"

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Abhängigkeiten installieren (minimal, für SQLite und PostgreSQL)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY . .

# Non-root User erstellen für Sicherheit
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Datenverzeichnis
VOLUME ["/app/data"]

# Port exponieren
EXPOSE 8000

# Health Check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Startup-Befehl (1 Worker für SQLite-Kompatibilität; bei PostgreSQL ggf. erhöhen)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
