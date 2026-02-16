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
STATION_CENTER: dict[str, str] = {
    "A1": "ZAPE",
    "B0": "ZDAP",
    "B2": "ZDAP",
}
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
