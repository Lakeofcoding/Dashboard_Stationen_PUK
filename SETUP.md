# PUK Dashboard — Setup-Anleitung

## Voraussetzungen

Das PUK Dashboard benötigt zwei Laufzeitumgebungen:

| Software | Version | Download |
|----------|---------|----------|
| **Python** | 3.11 oder neuer | https://www.python.org/downloads/ |
| **Node.js** | 20 LTS oder neuer | https://nodejs.org/ |

### Python installieren

1. Installationsprogramm von https://www.python.org/downloads/ herunterladen
2. **Wichtig:** Beim ersten Schritt das Häkchen bei **„Add Python to PATH"** setzen
3. „Install Now" klicken

### Node.js installieren

**Option A — Installer:**
1. https://nodejs.org/ aufrufen und die **LTS-Version** herunterladen
2. Installationsprogramm ausführen (Standard-Optionen reichen)

**Option B — winget (Windows 10/11):**
```
winget install OpenJS.NodeJS.LTS
```

**Option C — Automatisch:**
Die Skripte `demo-start.bat` und `demo-prepare.bat` versuchen Node.js bei Bedarf automatisch per winget zu installieren.

> **Hinweis:** Nach der Installation von Python oder Node.js muss ein **neues** Terminal/Fenster geöffnet werden, damit die Programme im PATH verfügbar sind.

---

## Schnellstart (mit Internet)

```
Doppelklick auf: demo-start.bat
```

Das Skript prüft Python und Node.js, installiert fehlende Pakete automatisch und startet Backend + Frontend. Der Browser öffnet sich unter http://localhost:5173.

---

## Offline-Vorbereitung (z.B. für Klinik-Demo)

Auf einem Rechner **mit Internet:**

```
Doppelklick auf: demo-prepare.bat
```

Das Skript erstellt eine Python-venv und installiert alle Pakete. Danach kann das gesamte Verzeichnis auf einen Rechner **ohne Internet** kopiert werden (z.B. USB-Stick).

Auf dem Ziel-Rechner genügt dann:

```
Doppelklick auf: demo-start.bat
```

**Voraussetzung am Ziel-PC:** Python und Node.js müssen installiert sein.

---

## Manueller Start (für Entwickler)

### Backend

```bash
cd backend
python -m venv .venv              # Einmalig
.venv\Scripts\activate            # Windows
pip install -r requirements.txt   # Einmalig
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install        # Einmalig
npm run dev        # Startet Vite Dev-Server auf Port 5173
```

---

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| „Python nicht gefunden" | Python installieren, dabei **„Add to PATH"** ankreuzen. Neues Terminal öffnen. |
| „Node.js nicht gefunden" | Node.js LTS installieren. Neues Terminal öffnen. |
| `npm install` schlägt fehl | Internetverbindung prüfen. Hinter einem Proxy: `npm config set proxy http://proxy:port` |
| Backend startet nicht (Port 8000 belegt) | Anderes Backend beenden oder `--port 8001` verwenden |
| Frontend zeigt leere Seite | Backend läuft? Prüfen: http://localhost:8000/health |
| „CSRF-Fehler" im Browser | Cookies löschen und Seite neu laden |
