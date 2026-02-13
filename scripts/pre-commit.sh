#!/bin/bash
# Pre-Commit Hook für PUK Dashboard
# Verhindert versehentliches Committen sensibler Daten
#
# Installation:
# cp scripts/pre-commit.sh .git/hooks/pre-commit
# chmod +x .git/hooks/pre-commit

set -e

echo "🔍 Pre-Commit Checks..."

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# 1. Check für .env Dateien
echo -n "  Checking for .env files... "
if git diff --cached --name-only | grep -E "\.env$" > /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "    ❌ .env Dateien dürfen nicht committed werden!"
    echo "    Nur .env.example ist erlaubt."
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 2. Check für Datenbank-Dateien
echo -n "  Checking for database files... "
if git diff --cached --name-only | grep -E "\.(db|sqlite|db-shm|db-wal)$" > /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "    ❌ Datenbank-Dateien dürfen nicht committed werden!"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 3. Check für Private Keys
echo -n "  Checking for private keys... "
if git diff --cached --name-only | grep -E "\.(key|pem|p12)$" > /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "    ❌ Private Keys dürfen nicht committed werden!"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 4. Check für Secrets in Code
echo -n "  Checking for hardcoded secrets... "
if git diff --cached -U0 | grep -iE "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}" > /dev/null; then
    echo -e "${YELLOW}WARNING${NC}"
    echo "    ⚠️  Möglicherweise hardcoded Secrets gefunden!"
    echo "    Bitte manuell prüfen."
    # Nicht als Error, nur Warnung
else
    echo -e "${GREEN}OK${NC}"
fi

# 5. Check für node_modules
echo -n "  Checking for node_modules... "
if git diff --cached --name-only | grep "node_modules/" > /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "    ❌ node_modules/ darf nicht committed werden!"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 6. Check für .venv
echo -n "  Checking for .venv... "
if git diff --cached --name-only | grep "\.venv/" > /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "    ❌ .venv/ darf nicht committed werden!"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 7. Check für __pycache__
echo -n "  Checking for __pycache__... "
if git diff --cached --name-only | grep "__pycache__/" > /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "    ❌ __pycache__/ darf nicht committed werden!"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK${NC}"
fi

# 8. Check für große Dateien (> 10MB)
echo -n "  Checking for large files... "
LARGE_FILES=$(git diff --cached --name-only --diff-filter=ACM | xargs -I {} du -k {} 2>/dev/null | awk '$1 > 10240 {print $2}')
if [ -n "$LARGE_FILES" ]; then
    echo -e "${YELLOW}WARNING${NC}"
    echo "    ⚠️  Große Dateien (>10MB) gefunden:"
    echo "$LARGE_FILES" | while read file; do
        size=$(du -h "$file" | cut -f1)
        echo "      - $file ($size)"
    done
    echo "    Erwägen Sie Git LFS: git lfs track \"$LARGE_FILES\""
    # Nicht als Error, nur Warnung
else
    echo -e "${GREEN}OK${NC}"
fi

echo ""

# Ergebnis
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ Pre-Commit Checks FAILED${NC}"
    echo ""
    echo "Bitte beheben Sie die Fehler und versuchen Sie es erneut."
    echo "Oder überspringen Sie die Checks mit: git commit --no-verify"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ All Pre-Commit Checks Passed${NC}"
    echo ""
    exit 0
fi
