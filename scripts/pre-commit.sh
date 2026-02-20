#!/bin/bash
# Pre-Commit Hook für PUK Dashboard
# Verhindert: (1) sensible Daten im Repo, (2) kaputten Code
#
# Installation (Linux/Mac):
#   cp scripts/pre-commit.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Installation (Windows, Git Bash):
#   cp scripts/pre-commit.sh .git/hooks/pre-commit

set -e

echo "Pre-Commit Checks..."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

# ── Phase 1: Security Checks (keine Daten/Secrets im Repo) ──────────

echo -n "  [1/9] .env files... "
if git diff --cached --name-only | grep -E "\.env$" > /dev/null 2>&1; then
    echo -e "${RED}BLOCKED${NC} — .env darf nicht committed werden"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

echo -n "  [2/9] Database files... "
if git diff --cached --name-only | grep -E "\.(db|sqlite|db-shm|db-wal)$" > /dev/null 2>&1; then
    echo -e "${RED}BLOCKED${NC} — DB-Dateien gehoeren nicht ins Repo"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

echo -n "  [3/9] Private keys... "
if git diff --cached --name-only | grep -E "\.(key|pem|p12|pfx)$" > /dev/null 2>&1; then
    echo -e "${RED}BLOCKED${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

echo -n "  [4/9] Hardcoded secrets... "
if git diff --cached -U0 2>/dev/null | grep -iE "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}" > /dev/null 2>&1; then
    echo -e "${YELLOW}WARNING${NC} — bitte manuell pruefen"
else
    echo -e "${GREEN}OK${NC}"
fi

echo -n "  [5/9] Build artifacts... "
if git diff --cached --name-only | grep -E "node_modules/|\.venv/|__pycache__/" > /dev/null 2>&1; then
    echo -e "${RED}BLOCKED${NC} — Build-Artefakte nicht committen"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# ── Phase 2: Python Compile Check (schnell, <1s) ────────────────────

echo -n "  [6/9] Python syntax... "
BACKEND_DIR="$(git rev-parse --show-toplevel)/backend"
if [ -d "$BACKEND_DIR" ]; then
    SYNTAX_ERRORS=$(find "$BACKEND_DIR" -name "*.py" \
        -not -path "*__pycache__*" -not -path "*.venv*" \
        -exec python -c "
import py_compile, sys
try:
    py_compile.compile(sys.argv[1], doraise=True)
except py_compile.PyCompileError as e:
    print(f'  {e}', file=sys.stderr)
    sys.exit(1)
" {} \; 2>&1 | grep -c "Error" || true)
    if [ "$SYNTAX_ERRORS" -gt 0 ]; then
        echo -e "${RED}FAILED${NC} — $SYNTAX_ERRORS Syntax-Fehler"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}OK${NC}"
    fi
else
    echo -e "${YELLOW}SKIP${NC} — backend/ nicht gefunden"
fi

# ── Phase 3: Smoke Tests (wenn pytest verfuegbar, ~5s) ──────────────

echo -n "  [7/9] Smoke tests... "
if python -c "import pytest" 2>/dev/null; then
    cd "$BACKEND_DIR" 2>/dev/null || cd "$(git rev-parse --show-toplevel)/backend"
    if python -m pytest -m smoke -q --tb=line --no-header -x 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED${NC} — Smoke-Tests fehlgeschlagen"
        echo "    Tipp: python -m pytest -m smoke -v  fuer Details"
        ERRORS=$((ERRORS + 1))
    fi
    cd - > /dev/null 2>/dev/null || true
else
    echo -e "${YELLOW}SKIP${NC} — pytest nicht installiert (pip install pytest httpx)"
fi

# ── Phase 4: Frontend Check ─────────────────────────────────────────

echo -n "  [8/9] JSX balance... "
FRONTEND_DIR="$(git rev-parse --show-toplevel)/frontend/src"
if [ -d "$FRONTEND_DIR" ]; then
    JSX_ERRORS=0
    for f in "$FRONTEND_DIR"/*.tsx; do
        [ -f "$f" ] || continue
        BRACES=$(python -c "s=open('$f').read(); print(s.count('{')-s.count('}'))" 2>/dev/null || echo "0")
        PARENS=$(python -c "s=open('$f').read(); print(s.count('(')-s.count(')'))" 2>/dev/null || echo "0")
        if [ "$BRACES" != "0" ] || [ "$PARENS" != "0" ]; then
            echo ""
            echo "    $(basename $f): braces=$BRACES parens=$PARENS"
            JSX_ERRORS=$((JSX_ERRORS + 1))
        fi
    done
    if [ "$JSX_ERRORS" -gt 0 ]; then
        echo -e "${RED}FAILED${NC}"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}OK${NC}"
    fi
else
    echo -e "${YELLOW}SKIP${NC}"
fi

echo -n "  [9/9] Large files (>10MB)... "
LARGE=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | xargs -I {} du -k {} 2>/dev/null | awk '$1 > 10240 {print $2}')
if [ -n "$LARGE" ]; then
    echo -e "${YELLOW}WARNING${NC}"
    echo "$LARGE"
else
    echo -e "${GREEN}OK${NC}"
fi

# ── Ergebnis ─────────────────────────────────────────────────────────

echo ""
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}COMMIT BLOCKIERT${NC} ($ERRORS Fehler)"
    echo "  Beheben und erneut committen, oder: git commit --no-verify"
    exit 1
else
    echo -e "${GREEN}Alle Checks bestanden${NC}"
    exit 0
fi
