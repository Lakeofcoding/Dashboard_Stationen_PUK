"""
Zentrale Konfiguration: Environment-Variablen, Konstanten, Startup-Checks.
"""
from __future__ import annotations
import os
import warnings

# --- Environment ---
DEBUG = os.getenv("DASHBOARD_DEBUG", "0") in ("1", "true", "True")
SECRET_KEY = os.getenv("SECRET_KEY", "")
DEMO_MODE = os.getenv("DASHBOARD_ALLOW_DEMO_AUTH", "1") in ("1", "true", "True")
SECURE_COOKIES = os.getenv("DASHBOARD_SECURE_COOKIES", "0") in ("1", "true", "True")

# --- Klinik-Konstanten ---
# Dynamisch aus Excel geladen (lazy); Fallback auf Hardcoded fuer Tests.
_STATION_CENTER_FALLBACK: dict[str, str] = {
    "A1": "ZAPE", "B0": "ZDAP", "B2": "ZDAP",
    "Station A1": "ZAPE", "Station B0": "ZAPE", "Station B2": "ZDAP",
}

def _load_station_center() -> dict[str, str]:
    try:
        from app.excel_loader import get_station_center_map
        m = get_station_center_map()
        if m:
            return m
    except Exception:
        pass
    return _STATION_CENTER_FALLBACK

# Lazy property — wird beim ersten Zugriff geladen
class _StationCenterProxy(dict):
    _loaded = False
    def _ensure(self):
        if not self._loaded:
            self.update(_load_station_center())
            self._loaded = True
    def __getitem__(self, key): self._ensure(); return super().__getitem__(key)
    def __contains__(self, key): self._ensure(); return super().__contains__(key)
    def get(self, key, default=None): self._ensure(); return super().get(key, default)
    def keys(self): self._ensure(); return super().keys()
    def values(self): self._ensure(); return super().values()
    def items(self): self._ensure(); return super().items()
    def __iter__(self): self._ensure(); return super().__iter__()
    def __len__(self): self._ensure(); return super().__len__()

STATION_CENTER: dict[str, str] = _StationCenterProxy(_STATION_CENTER_FALLBACK)
CLINIC_DEFAULT = "EPP"

# --- Startup-Warnungen ---
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
