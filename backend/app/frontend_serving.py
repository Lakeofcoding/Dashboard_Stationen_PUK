"""
Production Frontend-Serving mit Nonce-Injection.

In Produktion liefert das Backend das gebaute Frontend (dist/) aus
und injiziert den pro-Request CSP-Nonce in alle <script>-Tags.

Ablauf:
  1. vite build → frontend/dist/index.html + frontend/dist/assets/
  2. Backend liest dist/index.html beim Start (einmalig)
  3. Pro Request: Nonce aus scope["state"]["csp_nonce"] lesen,
     in <script>-Tags injizieren, HTML ausliefern
  4. Statische Assets (JS/CSS/Bilder) direkt aus dist/assets/ servieren

Aktivierung:
  - Automatisch wenn frontend/dist/index.html existiert
  - Oder manuell mit DASHBOARD_SERVE_FRONTEND=1

Dev-Modus:
  - Vite Dev-Server (port 5173) serviert das Frontend
  - Backend-Proxy in vite.config.ts leitet /api/ weiter
  - Nonce-CSP ist im Dev-Modus unwirksam (Vite braucht unsafe-inline für HMR)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Pfad zum gebauten Frontend
_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
_INDEX_HTML: str | None = None
_NONCE_PLACEHOLDER = "__CSP_NONCE__"

# Regex: <script ...> Tags (mit oder ohne type="module", crossorigin, etc.)
_SCRIPT_TAG_RE = re.compile(r"<script\b", re.IGNORECASE)
# Regex: <link rel="modulepreload" ...> Tags (Vite generiert diese)
_MODULEPRELOAD_RE = re.compile(r'<link\b([^>]*)\brel="modulepreload"', re.IGNORECASE)


def _inject_nonce(html: str, nonce: str) -> str:
    """Injiziert nonce-Attribut in alle <script>-Tags und modulepreload-Links.

    Vite generiert beim Build:
      <script type="module" crossorigin src="/assets/index-xxx.js">
      <link rel="modulepreload" crossorigin href="/assets/xxx.js">

    Wir fügen nonce="..." hinzu:
      <script nonce="..." type="module" crossorigin src="/assets/index-xxx.js">
      <link nonce="..." rel="modulepreload" crossorigin href="/assets/xxx.js">
    """
    nonce_attr = f'nonce="{nonce}"'

    # Script-Tags
    html = _SCRIPT_TAG_RE.sub(f"<script {nonce_attr}", html)

    # Modulepreload-Links (werden von CSP als Script-Ressourcen behandelt)
    html = _MODULEPRELOAD_RE.sub(
        lambda m: f'<link {nonce_attr}{m.group(1)}rel="modulepreload"', html
    )

    return html


def setup_production_serving(app: FastAPI) -> bool:
    """Konfiguriert Production-Frontend-Serving falls dist/ existiert.

    Returns:
        True wenn Production-Serving aktiviert wurde, False sonst.
    """
    force = os.getenv("DASHBOARD_SERVE_FRONTEND", "0") in ("1", "true", "True")
    index_path = _DIST_DIR / "index.html"
    assets_dir = _DIST_DIR / "assets"

    if not index_path.exists() and not force:
        return False

    global _INDEX_HTML
    if index_path.exists():
        _INDEX_HTML = index_path.read_text(encoding="utf-8")
    else:
        return False

    # Statische Assets (JS, CSS, Bilder) direkt servieren
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Favicons und andere Root-Level Dateien aus dist/
    for static_file in _DIST_DIR.iterdir():
        if static_file.is_file() and static_file.name != "index.html":
            # Einzelne Dateien (favicon.ico etc.) können über StaticFiles nicht
            # einzeln gemountet werden, daher über Catch-All abgefangen
            pass

    # Catch-All: Alle nicht-API-Routen liefern index.html (SPA Routing)
    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(request: Request, path: str) -> HTMLResponse:
        """Liefert index.html mit injiziertem CSP-Nonce für alle Frontend-Routen."""
        # API-Routen nicht abfangen (sollte durch Router-Priorität nicht passieren,
        # aber als Safety-Check)
        if path.startswith("api/") or path == "health":
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        # Nonce aus ASGI-Scope lesen (gesetzt von SecurityHeadersMiddleware)
        nonce = request.scope.get("state", {}).get("csp_nonce", "")

        if _INDEX_HTML and nonce:
            html = _inject_nonce(_INDEX_HTML, nonce)
        elif _INDEX_HTML:
            html = _INDEX_HTML
        else:
            html = "<html><body>Frontend nicht gebaut. Bitte 'npm run build' ausführen.</body></html>"

        return HTMLResponse(content=html)

    return True
