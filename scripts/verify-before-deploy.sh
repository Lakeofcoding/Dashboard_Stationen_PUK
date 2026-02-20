#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# PUK Dashboard — Pre-Deployment Verification
# ═══════════════════════════════════════════════════════════════════════
#
# Ausfuehren BEVOR eine neue Version auf den Klinik-Server deployed wird.
# Funktioniert komplett offline (kein Internet noetig).
#
# Verwendung:
#   cd Dashboard_Stationen_PUK/backend
#   bash ../scripts/verify-before-deploy.sh
#
# Bei Erfolg: "DEPLOYMENT FREIGEGEBEN"
# Bei Fehler: "DEPLOYMENT BLOCKIERT" + Fehlerliste
#
# Das Ergebnis wird zusaetzlich als Log-Datei geschrieben:
#   data/deploy-verification-YYYY-MM-DD_HH-MM-SS.log
#
# Dieses Log dient als Nachweis fuer den Datenschutzbeauftragten,
# dass technische Massnahmen vor Deployment geprueft wurden (Art. 8 nDSG).
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_DIR="$BACKEND_DIR/data"
LOG_FILE="$LOG_DIR/deploy-verification-${TIMESTAMP}.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ERRORS=0
WARNINGS=0
TOTAL_TESTS=0
PASSED_TESTS=0

mkdir -p "$LOG_DIR"

# Logging: Stdout + Datei
log() {
    echo -e "$1"
    echo -e "$1" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
}

section() {
    log ""
    log "${CYAN}── $1 ──${NC}"
}

pass() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    log "  ${GREEN}PASS${NC}  $1"
}

fail() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    ERRORS=$((ERRORS + 1))
    log "  ${RED}FAIL${NC}  $1"
}

warn() {
    WARNINGS=$((WARNINGS + 1))
    log "  ${YELLOW}WARN${NC}  $1"
}

# ═══════════════════════════════════════════════════════════════════════

log "${BOLD}PUK Dashboard — Pre-Deployment Verification${NC}"
log "Zeitstempel: $TIMESTAMP"
log "Verzeichnis: $PROJECT_DIR"
log ""

# ── 1. Verzeichnisstruktur ──────────────────────────────────────────

section "1. Verzeichnisstruktur"

for dir in backend backend/app backend/routers backend/middleware backend/tests frontend frontend/src rules; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        pass "$dir/"
    else
        fail "$dir/ nicht gefunden"
    fi
done

if [ -f "$PROJECT_DIR/rules/rules.yaml" ]; then
    pass "rules/rules.yaml vorhanden"
else
    fail "rules/rules.yaml fehlt"
fi

# ── 2. Python Syntax ────────────────────────────────────────────────

section "2. Python Syntax (Compile-Check)"

cd "$BACKEND_DIR"
PY_FILES=$(find . -name "*.py" -not -path "*__pycache__*" -not -path "*.venv*" | sort)
PY_COUNT=$(echo "$PY_FILES" | wc -l)
PY_ERRORS=0

for f in $PY_FILES; do
    if python -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null; then
        : # ok
    else
        fail "Syntax-Fehler: $f"
        PY_ERRORS=$((PY_ERRORS + 1))
    fi
done

if [ "$PY_ERRORS" -eq 0 ]; then
    pass "$PY_COUNT Python-Dateien kompiliert"
fi

# ── 3. JSX Balance ──────────────────────────────────────────────────

section "3. Frontend Integrity (JSX Balance)"

JSX_ERRORS=0
for f in "$PROJECT_DIR"/frontend/src/*.tsx; do
    [ -f "$f" ] || continue
    bn=$(basename "$f")
    BRACES=$(python -c "s=open('$f').read(); print(s.count('{')-s.count('}'))" 2>/dev/null || echo "999")
    PARENS=$(python -c "s=open('$f').read(); print(s.count('(')-s.count(')'))" 2>/dev/null || echo "999")
    if [ "$BRACES" = "0" ] && [ "$PARENS" = "0" ]; then
        pass "$bn (braces=0, parens=0)"
    else
        fail "$bn (braces=$BRACES, parens=$PARENS)"
        JSX_ERRORS=$((JSX_ERRORS + 1))
    fi
done

# ── 4. Pytest Suite ─────────────────────────────────────────────────

section "4. Test-Suite (pytest)"

if python -c "import pytest" 2>/dev/null; then
    cd "$BACKEND_DIR"

    log "  Starte vollstaendige Test-Suite..."
    PYTEST_OUTPUT=$(python -m pytest -v --tb=short --no-header 2>&1) || true
    PYTEST_EXIT=$?

    # Ergebnis parsen
    PYTEST_SUMMARY=$(echo "$PYTEST_OUTPUT" | tail -3)
    echo "$PYTEST_OUTPUT" >> "$LOG_FILE"

    if [ "$PYTEST_EXIT" -eq 0 ]; then
        PYTEST_PASSED=$(echo "$PYTEST_SUMMARY" | grep -oP '\d+ passed' || echo "? passed")
        pass "Alle Tests bestanden ($PYTEST_PASSED)"
    else
        PYTEST_FAILED=$(echo "$PYTEST_SUMMARY" | grep -oP '\d+ failed' || echo "? failed")
        fail "Tests fehlgeschlagen ($PYTEST_FAILED)"
        log ""
        log "  Fehlgeschlagene Tests:"
        echo "$PYTEST_OUTPUT" | grep "FAILED" | while read line; do
            log "    $line"
        done
    fi
else
    warn "pytest nicht installiert — Test-Suite uebersprungen"
    warn "  Installation: pip install pytest httpx"
fi

# ── 5. Production Safety Checks ─────────────────────────────────────

section "5. Production Safety"

# 5a: SECRET_KEY
if [ -n "${SECRET_KEY:-}" ]; then
    KEY_LEN=${#SECRET_KEY}
    if [ "$KEY_LEN" -ge 32 ]; then
        pass "SECRET_KEY gesetzt ($KEY_LEN Zeichen)"
    else
        fail "SECRET_KEY zu kurz ($KEY_LEN < 32 Zeichen)"
    fi
else
    warn "SECRET_KEY nicht gesetzt (OK fuer Demo, NICHT fuer Produktion)"
fi

# 5b: DEMO_MODE
DEMO="${DASHBOARD_ALLOW_DEMO_AUTH:-1}"
if [ "$DEMO" = "0" ] || [ "$DEMO" = "false" ]; then
    pass "Demo-Modus deaktiviert"
else
    warn "Demo-Modus aktiv (DASHBOARD_ALLOW_DEMO_AUTH=$DEMO)"
fi

# 5c: SECURE_COOKIES
SECURE="${DASHBOARD_SECURE_COOKIES:-0}"
if [ "$SECURE" = "1" ] || [ "$SECURE" = "true" ]; then
    pass "Secure Cookies aktiviert"
else
    warn "Secure Cookies deaktiviert (OK ohne HTTPS)"
fi

# 5d: Keine app.db im Repo
if [ -f "$BACKEND_DIR/data/app.db" ]; then
    warn "data/app.db existiert — wird beim Start ueberschrieben"
fi

# 5e: CSP Nonce
NONCE="${DASHBOARD_CSP_NONCE:-1}"
if [ "$NONCE" = "1" ] || [ "$NONCE" = "true" ]; then
    pass "CSP Nonce aktiviert"
else
    warn "CSP Nonce deaktiviert (DASHBOARD_CSP_NONCE=$NONCE)"
fi

# ── 6. Dependency Check ─────────────────────────────────────────────

section "6. Dependencies"

for pkg in fastapi uvicorn sqlalchemy pydantic yaml; do
    if python -c "import $pkg" 2>/dev/null; then
        pass "$pkg verfuegbar"
    else
        fail "$pkg fehlt (pip install)"
    fi
done

# ═══════════════════════════════════════════════════════════════════════
# Ergebnis
# ═══════════════════════════════════════════════════════════════════════

section "Ergebnis"

log ""
log "  Checks:    $TOTAL_TESTS ausgefuehrt, $PASSED_TESTS bestanden"
log "  Fehler:    $ERRORS"
log "  Warnungen: $WARNINGS"
log "  Log:       $LOG_FILE"
log ""

if [ "$ERRORS" -gt 0 ]; then
    log "${RED}${BOLD}DEPLOYMENT BLOCKIERT${NC} — $ERRORS Fehler muessen behoben werden"
    log ""
    exit 1
else
    if [ "$WARNINGS" -gt 0 ]; then
        log "${YELLOW}${BOLD}DEPLOYMENT FREIGEGEBEN (mit $WARNINGS Warnungen)${NC}"
    else
        log "${GREEN}${BOLD}DEPLOYMENT FREIGEGEBEN${NC}"
    fi
    log ""
    exit 0
fi
