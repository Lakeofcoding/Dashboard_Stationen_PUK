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
from pathlib import Path

# ── dotenv laden (non-Docker / Demo-Modus) ───────────────────────────
# Muss ZUERST geschehen, bevor os.getenv aufgerufen wird.
# Lädt .env aus dem Projektroot (zwei Ebenen über app/).
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_ENV_FILE, override=False)
    except ImportError:
        # python-dotenv nicht installiert → manuell lesen
        with open(_ENV_FILE) as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v

# ── Environment ──────────────────────────────────────────────────────
# HINWEIS: Env-Var-Namen sind kanonisch mit DASHBOARD_-Prefix.
# Für Rückwärtskompatibilität werden auch die Kurzformen (ohne Prefix) akzeptiert.

def _env_bool(primary: str, fallback: str | None = None, default: str = "0") -> bool:
    """Liest eine bool-Env-Var mit optionalem Fallback-Namen."""
    val = os.getenv(primary)
    if val is None and fallback:
        val = os.getenv(fallback)
    if val is None:
        val = default
    return val.lower() in ("1", "true", "yes")

DEBUG = _env_bool("DASHBOARD_DEBUG", "DEBUG", "0")
DEMO_MODE = _env_bool("DASHBOARD_ALLOW_DEMO_AUTH", "ALLOW_DEMO_AUTH", "1")
SECURE_COOKIES = _env_bool("DASHBOARD_SECURE_COOKIES", default="0")

# SECRET_KEY: beide Varianten akzeptieren
SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("DASHBOARD_SECRET_KEY", ""))

# ── Rollen-Scope Mapping (echte Konfiguration, nicht Daten) ─────────
ROLE_SCOPE: dict[str, str] = {
    "system_admin":  "global",
    "admin":         "global",
    "manager":       "klinik",
    "shift_lead":    "zentrum",
    "clinician":     "station",
    "viewer":        "station",
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
    """Lazy-loading dict: lädt Station→Center aus Excel beim ersten Zugriff."""
    _loaded = False

    def _ensure(self):
        if not self._loaded:
            try:
                from app.excel_loader import get_station_center_map
                m = get_station_center_map()
                if m:
                    self.update(m)
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
        self._loaded = False
        self.clear()


STATION_CENTER: dict[str, str] = _StationCenterProxy()


# ── Startup-Warnungen ────────────────────────────────────────────────
if not SECRET_KEY or SECRET_KEY in ("change_this_in_production_to_random_string", "CHANGE_THIS_TO_A_RANDOM_STRING_IN_PRODUCTION"):
    warnings.warn(
        "SECRET_KEY nicht gesetzt oder Default! "
        "Im Demo-Modus wird ein temporärer Key verwendet. "
        "Für Produktion: SECRET_KEY=<random 64 hex> in .env setzen.",
        stacklevel=1,
    )
if DEMO_MODE:
    warnings.warn(
        "DEMO-MODUS aktiv (ALLOW_DEMO_AUTH=1). "
        "Authentifizierung ist vereinfacht. Nur für Demo/Pilot!",
        stacklevel=1,
    )
