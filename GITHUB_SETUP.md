# GitHub Setup Guide - PUK Dashboard

## 🚀 Quick Start für GitHub Push

### ✅ Pre-Push Checkliste

Bevor Sie auf GitHub pushen, stellen Sie sicher:

- [ ] **Keine sensiblen Daten**: Keine .env, Passwörter, API-Keys im Code
- [ ] **Datenbank-Dateien entfernt**: Keine *.db, *.db-* Dateien
- [ ] **Secrets in .env.example**: Nur Platzhalter, keine echten Werte
- [ ] **.gitignore funktioniert**: Teste mit `git status`
- [ ] **README.md aktuell**: Projekt-Beschreibung korrekt
- [ ] **LICENSE vorhanden**: MIT License (bereits erstellt)

---

## 📋 Schritt-für-Schritt Anleitung

### 1. Datenbank-Dateien entfernen

**WICHTIG**: Datenbank-Dateien dürfen NICHT auf GitHub!

```bash
# Im Projekt-Verzeichnis
cd dashboard_improved

# Datenbank-Dateien löschen
rm -f backend/data/*.db backend/data/*.db-* backend/data/*.sqlite*

# .gitkeep erstellen damit Verzeichnis erhalten bleibt
touch backend/data/.gitkeep
echo "*.db" >> backend/data/.gitignore
echo "*.db-*" >> backend/data/.gitignore
```

### 2. Git Repository initialisieren

```bash
cd dashboard_improved

# Git initialisieren
git init

# Überprüfen was committed wird
git status

# WICHTIG: Prüfen dass keine sensiblen Dateien dabei sind!
# Sollte NICHT dabei sein:
# - *.db, *.db-shm, *.db-wal
# - .env (nur .env.example ist OK)
# - *.key, *.pem, *.crt
# - node_modules/
# - .venv/
```

### 3. Ersten Commit erstellen

```bash
# Alle Dateien stagen
git add .

# Commit erstellen
git commit -m "Initial commit: PUK Dashboard v1.0.0

- Complete Docker setup
- Backend with FastAPI (refactored)
- Frontend with React + TypeScript
- RBAC and Break-Glass access
- CSRF protection and rate limiting
- Comprehensive documentation
- Production-ready deployment"
```

### 4. GitHub Repository erstellen

**Option A: Via GitHub Web UI**
1. Gehe zu https://github.com/new
2. Repository-Name: `puk-dashboard` (oder Ihr Wunschname)
3. Beschreibung: "Klinisches Qualitäts-Dashboard für psychiatrische Stationen"
4. Visibility: **Private** (empfohlen für medizinische Daten!)
5. **NICHT** "Initialize with README" anklicken (haben wir schon)
6. Klicke "Create repository"

**Option B: Via GitHub CLI**
```bash
# GitHub CLI installiert?
gh repo create puk-dashboard --private --source=. --remote=origin --push
```

### 5. Remote hinzufügen und pushen

```bash
# Remote hinzufügen (ersetze USERNAME)
git remote add origin https://github.com/USERNAME/puk-dashboard.git

# Branch umbenennen (optional, falls nicht schon 'main')
git branch -M main

# Pushen
git push -u origin main
```

---

## 🔒 Sicherheits-Best-Practices

### Was NIEMALS committen:

❌ `.env` Dateien mit echten Secrets  
❌ Datenbank-Dateien (*.db, *.sqlite)  
❌ Private Keys (*.key, *.pem)  
❌ Passwörter im Code  
❌ API-Keys oder Tokens  
❌ Patientendaten (auch nicht in Kommentaren!)  

### Was committen:

✅ `.env.example` (nur Platzhalter)  
✅ Quellcode  
✅ Dokumentation  
✅ Tests  
✅ Docker-Konfiguration  
✅ README, LICENSE, etc.  

### Secrets-Management

**Für GitHub Secrets** (bei CI/CD):
```bash
# In GitHub Repository:
# Settings → Secrets and variables → Actions → New repository secret

# Beispiele:
SECRET_KEY=<random-32-byte-string>
DB_PASSWORD=<secure-password>
DOCKER_USERNAME=<username>
DOCKER_PASSWORD=<password>
```

---

## 🏷️ GitHub Repository Settings

### Nach dem ersten Push konfigurieren:

1. **Description**: 
   ```
   🏥 Klinisches Qualitäts-Dashboard für psychiatrische Stationen. 
   Offline-fähig, DSGVO-konform, produktionsbereit.
   ```

2. **Topics** (Tags):
   ```
   healthcare, psychiatry, dashboard, quality-assurance, 
   fastapi, react, typescript, docker, offline-first, 
   gdpr-compliant, clinical-data
   ```

3. **Features aktivieren**:
   - ✅ Issues
   - ✅ Projects (optional)
   - ✅ Discussions (optional)
   - ✅ Wiki (optional)
   - ❌ Sponsorships (nur wenn relevant)

4. **Branch Protection** (für `main`):
   - Settings → Branches → Add branch protection rule
   - Branch name: `main`
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass (wenn CI/CD aktiv)
   - ✅ Require conversation resolution before merging

5. **Visibility**:
   - **Private** für interne Projekte mit Patientendaten
   - **Public** nur wenn keinerlei medizinische Daten

---

## 📝 README.md für GitHub optimieren

Stellen Sie sicher, dass `README.md` enthält:

- ✅ Projekt-Beschreibung
- ✅ Badges (Build-Status, Version, License)
- ✅ Screenshot oder Demo (optional)
- ✅ Installation-Anleitung
- ✅ Quick-Start
- ✅ Dokumentations-Links
- ✅ Contribution-Guidelines
- ✅ License

**Badges hinzufügen** (oben in README.md):
```markdown
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](docker-compose.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](backend/requirements.txt)
[![React](https://img.shields.io/badge/react-19-blue.svg)](frontend/package.json)
```

---

## 🔄 .gitignore verifizieren

**Test ob .gitignore funktioniert**:

```bash
# Zeige was committed wird
git status

# Zeige ignorierte Dateien
git status --ignored

# Sollte anzeigen:
# - node_modules/
# - .venv/
# - *.db
# - .env
# - __pycache__/
# etc.

# Test: Fake-Datei erstellen
touch backend/data/test.db
git status  # Sollte test.db NICHT zeigen!
rm backend/data/test.db
```

---

## 🚫 Falls versehentlich Secrets committed

**WICHTIG**: Secrets aus Git-History entfernen!

```bash
# Option 1: BFG Repo-Cleaner (empfohlen)
# Download: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files .env
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Option 2: git-filter-repo
pip install git-filter-repo
git filter-repo --invert-paths --path backend/data/app.db

# Danach: Force-Push
git push origin main --force
```

**Dann**: Alle Secrets ändern (neu generieren)!

---

## 📦 .dockerignore verifizieren

Stellen Sie sicher, dass `.dockerignore` funktioniert:

```bash
# In .dockerignore sollte sein:
.git
.env
*.db
node_modules
.venv
```

Dies verhindert, dass sensible Dateien in Docker-Images gelangen.

---

## 🎯 GitHub Actions (CI/CD) - Optional

Wenn Sie automatische Tests/Deployment wollen:

```bash
# Erstelle .github/workflows/ci.yml
mkdir -p .github/workflows
```

**Beispiel**: `.github/workflows/ci.yml`
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: |
          cd backend
          pip install -r requirements.txt
          pytest

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: |
          cd frontend
          npm ci
          npm run build
```

---

## 📊 GitHub Insights nutzen

Nach dem Push:

1. **Pulse**: Überblick über Aktivität
2. **Contributors**: Wer hat beigetragen
3. **Traffic**: Wer besucht das Repo
4. **Dependency Graph**: Zeigt Dependencies
5. **Security**: Dependabot-Alerts aktivieren

---

## ✅ Final Checklist vor dem Push

```bash
# 1. Datenbank-Dateien entfernt?
ls -la backend/data/*.db 2>/dev/null && echo "❌ DB-Dateien vorhanden!" || echo "✅ Keine DB-Dateien"

# 2. .env nicht in Git?
git ls-files | grep -E "^\.env$" && echo "❌ .env committed!" || echo "✅ .env nicht committed"

# 3. node_modules nicht in Git?
git ls-files | grep "node_modules" && echo "❌ node_modules committed!" || echo "✅ node_modules nicht committed"

# 4. .venv nicht in Git?
git ls-files | grep ".venv" && echo "❌ .venv committed!" || echo "✅ .venv nicht committed"

# 5. Secrets in .env.example sicher?
grep -E "password.*=.*[^=]$|secret.*=.*[^=]$|key.*=.*[^=]$" .env.example && echo "⚠️ Mögl. echte Secrets in .env.example!" || echo "✅ .env.example sauber"

# Wenn alles ✅ ist: Git Push!
```

---

## 🆘 Hilfe & Support

### Bei Problemen:

1. **Git-Fehler**: https://stackoverflow.com/questions/tagged/git
2. **GitHub-Docs**: https://docs.github.com
3. **Secrets entfernen**: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

### Häufige Fehler:

**"remote: Permission denied"**
→ SSH-Key einrichten oder HTTPS mit Token verwenden

**"failed to push some refs"**
→ `git pull --rebase` dann `git push`

**"large files detected"**
→ Git LFS aktivieren oder Dateien in .gitignore

---

## 📞 Kontakt

Bei Fragen zur GitHub-Integration:
- Issues im Repository erstellen
- Oder: Siehe README.md für Kontaktinformationen

---

*Letzte Aktualisierung: 2026-02-13*
