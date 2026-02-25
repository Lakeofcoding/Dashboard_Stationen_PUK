"""
Zentrale Konfiguration: Environment-Variablen, Konstanten, Startup-Checks.

ARCHITEKTUR-REGEL:
  Stations-/Klinik-/Zentrumsdaten kommen AUSSCHLIESSLICH aus der Excel
  (via excel_loader) oder aus der DB. Keine statischen Fallbacks.
  Wenn keine Daten vorhanden → leere Antwort, kein stilles Raten.
"""
from __future__ import annotations
import os
import warnings

# ── Environment ──────────────────────────────────────────────────────
DEBUG = os.getenv("DASHBOARD_DEBUG", "0") in ("1", "true", "True")
SECRET_KEY = os.getenv("SECRET_KEY", "")
DEMO_MODE = os.getenv("DASHBOARD_ALLOW_DEMO_AUTH", "1") in ("1", "true", "True")
SECURE_COOKIES = os.getenv("DASHBOARD_SECURE_COOKIES", "0") in ("1", "true", "True")

# ── Rollen-Scope Mapping (echte Konfiguration, nicht Daten) ─────────
ROLE_SCOPE: dict[str, str] = {
    "system_admin":  "global",
    "admin":         "global",
    "manager":       "klinik",      # Klinikmanager → ganze Klinik
    "shift_lead":    "zentrum",     # Schichtleitung → Zentrum
    "clinician":     "station",     # Arzt/Psychologe → Station
    "viewer":        "station",     # Lesezugriff → Station
}

# ── Display-Labels (UI-Texte, keine Daten) ───────────────────────────
CLINIC_LABELS: dict[str, str] = {
    "EPP": "Erwachsenenpsychiatrie",
    "KPP": "Kinder- und Jugendpsychiatrie",
    "FPK": "Forensische Psychiatrie",
    "APP": "Alterspsychiatrie",
}

CLINIC_DEFAULT = "EPP"


# ── Station-Center Proxy (lazy aus Excel) ────────────────────────────
class _StationCenterProxy(dict):
    """Lazy-loading dict: lädt Station→Center aus Excel beim ersten Zugriff.
    Kein statischer Fallback. Wenn Excel fehlt → leere Map → expliziter Hinweis."""
    _loaded = False

    def _ensure(self):
        if not self._loaded:
            try:
                from app.excel_loader import get_station_center_map
                m = get_station_center_map()
                if m:
                    self.update(m)
                    print(f"[config] STATION_CENTER: {len(m)} Stationen aus Excel geladen")
                else:
                    print("[config] WARNUNG: Keine Stations-Zuordnung in Excel gefunden")
            except Exception as e:
                print(f"[config] WARNUNG: Station-Center-Map nicht geladen: {e}")
            self._loaded = True

    def __getitem__(self, key): self._ensure(); return super().__getitem__(key)
    def __contains__(self, key): self._ensure(); return super().__contains__(key)
    def get(self, key, default=None): self._ensure(); return super().get(key, default)
    def keys(self): self._ensure(); return super().keys()
    def values(self): self._ensure(); return super().values()
    def items(self): self._ensure(); return super().items()
    def __iter__(self): self._ensure(); return super().__iter__()
    def __len__(self): self._ensure(); return super().__len__()
    def __bool__(self): self._ensure(); return super().__bool__()

    def reload(self):
        """Cache leeren — wird beim nächsten Zugriff neu geladen."""
        self._loaded = False
        self.clear()


STATION_CENTER: dict[str, str] = _StationCenterProxy()


# ── Startup-Warnungen ────────────────────────────────────────────────
if not SECRET_KEY or SECRET_KEY == "change_this_in_production_to_random_string":
    warnings.warn(
        "SECRET_KEY nicht gesetzt oder Default! "
        "Fuer Produktion: SECRET_KEY=<random 64 hex> setzen.",
        stacklevel=1,
    )
if DEMO_MODE:
    warnings.warn(
        "DEMO-MODUS aktiv (DASHBOARD_ALLOW_DEMO_AUTH=1). "
        "Authentifizierung ist NICHT sicher. Nur fuer Demo/Pilot!",
        stacklevel=1,
    )
