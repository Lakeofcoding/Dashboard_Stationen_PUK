# ═══════════════════════════════════════════════════════════════════════
# PUK Dashboard — Pre-Deployment Verification (Windows PowerShell)
# ═══════════════════════════════════════════════════════════════════════
#
# Ausfuehren BEVOR eine neue Version deployed wird:
#   cd C:\dev\Dashboard_Stationen_PUK\backend
#   powershell ..\scripts\verify-before-deploy.ps1
#
# Ergebnis + Log-Datei in data\deploy-verification-*.log
# ═══════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "backend"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$LogDir = Join-Path $BackendDir "data"
$LogFile = Join-Path $LogDir "deploy-verification-$Timestamp.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Errors = 0
$Warnings = 0
$TotalTests = 0
$PassedTests = 0

function Log($msg) {
    Write-Host $msg
    $msg -replace '\x1b\[[0-9;]*m', '' | Out-File -Append -FilePath $LogFile
}

function Pass($msg) {
    $script:TotalTests++; $script:PassedTests++
    Log "  PASS  $msg"
}

function Fail($msg) {
    $script:TotalTests++; $script:Errors++
    Log "  FAIL  $msg"
}

function Warn($msg) {
    $script:Warnings++
    Log "  WARN  $msg"
}

# ═══════════════════════════════════════════════════════════════════════

Log "PUK Dashboard - Pre-Deployment Verification"
Log "Zeitstempel: $Timestamp"
Log "Verzeichnis: $ProjectDir"
Log ""

# -- 1. Verzeichnisstruktur --

Log "-- 1. Verzeichnisstruktur --"
foreach ($dir in @("backend", "backend\app", "backend\routers", "backend\middleware", "backend\tests", "frontend\src", "rules")) {
    $full = Join-Path $ProjectDir $dir
    if (Test-Path $full) { Pass "$dir/" } else { Fail "$dir/ nicht gefunden" }
}

$rulesYaml = Join-Path $ProjectDir "rules\rules.yaml"
if (Test-Path $rulesYaml) { Pass "rules/rules.yaml" } else { Fail "rules/rules.yaml fehlt" }

# -- 2. Python Syntax --

Log ""
Log "-- 2. Python Syntax --"
Set-Location $BackendDir
$pyFiles = Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.FullName -notmatch "__pycache__|\.venv" }
$pyErrors = 0
foreach ($f in $pyFiles) {
    $result = & python -c "import py_compile; py_compile.compile(r'$($f.FullName)', doraise=True)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "Syntax: $($f.Name)"
        $pyErrors++
    }
}
if ($pyErrors -eq 0) { Pass "$($pyFiles.Count) Python-Dateien kompiliert" }

# -- 3. JSX Balance --

Log ""
Log "-- 3. Frontend Integrity --"
$tsxFiles = Get-ChildItem (Join-Path $ProjectDir "frontend\src") -Filter "*.tsx" -ErrorAction SilentlyContinue
foreach ($f in $tsxFiles) {
    $content = Get-Content $f.FullName -Raw
    $braces = ($content.ToCharArray() | Where-Object { $_ -eq '{' }).Count - ($content.ToCharArray() | Where-Object { $_ -eq '}' }).Count
    $parens = ($content.ToCharArray() | Where-Object { $_ -eq '(' }).Count - ($content.ToCharArray() | Where-Object { $_ -eq ')' }).Count
    if ($braces -eq 0 -and $parens -eq 0) {
        Pass "$($f.Name)"
    } else {
        Fail "$($f.Name) (braces=$braces, parens=$parens)"
    }
}

# -- 4. Pytest --

Log ""
Log "-- 4. Test-Suite --"
$pytestAvailable = & python -c "import pytest" 2>&1
if ($LASTEXITCODE -eq 0) {
    Set-Location $BackendDir
    Log "  Starte vollstaendige Test-Suite..."
    $pytestOutput = & python -m pytest -v --tb=short --no-header 2>&1
    $pytestOutput | Out-File -Append -FilePath $LogFile

    if ($LASTEXITCODE -eq 0) {
        $passLine = ($pytestOutput | Select-String "passed" | Select-Object -Last 1)
        Pass "Alle Tests bestanden ($passLine)"
    } else {
        $failLine = ($pytestOutput | Select-String "failed" | Select-Object -Last 1)
        Fail "Tests fehlgeschlagen ($failLine)"
        Log ""
        Log "  Fehlgeschlagene Tests:"
        $pytestOutput | Select-String "FAILED" | ForEach-Object { Log "    $_" }
    }
} else {
    Warn "pytest nicht installiert (pip install pytest httpx)"
}

# -- 5. Production Safety --

Log ""
Log "-- 5. Production Safety --"

$sk = $env:SECRET_KEY
if ($sk -and $sk.Length -ge 32) {
    Pass "SECRET_KEY gesetzt ($($sk.Length) Zeichen)"
} elseif ($sk) {
    Fail "SECRET_KEY zu kurz ($($sk.Length) < 32)"
} else {
    Warn "SECRET_KEY nicht gesetzt (OK fuer Demo)"
}

$demo = if ($env:DASHBOARD_ALLOW_DEMO_AUTH) { $env:DASHBOARD_ALLOW_DEMO_AUTH } else { "1" }
if ($demo -eq "0" -or $demo -eq "false") { Pass "Demo-Modus deaktiviert" } else { Warn "Demo-Modus aktiv" }

$nonce = if ($env:DASHBOARD_CSP_NONCE) { $env:DASHBOARD_CSP_NONCE } else { "1" }
if ($nonce -eq "1" -or $nonce -eq "true") { Pass "CSP Nonce aktiviert" } else { Warn "CSP Nonce deaktiviert" }

# -- 6. Dependencies --

Log ""
Log "-- 6. Dependencies --"
foreach ($pkg in @("fastapi", "uvicorn", "sqlalchemy", "pydantic", "yaml")) {
    & python -c "import $pkg" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Pass $pkg } else { Fail "$pkg fehlt" }
}

# ═══════════════════════════════════════════════════════════════════════

Log ""
Log "-- Ergebnis --"
Log ""
Log "  Checks:    $TotalTests ausgefuehrt, $PassedTests bestanden"
Log "  Fehler:    $Errors"
Log "  Warnungen: $Warnings"
Log "  Log:       $LogFile"
Log ""

if ($Errors -gt 0) {
    Log "DEPLOYMENT BLOCKIERT - $Errors Fehler muessen behoben werden"
    exit 1
} elseif ($Warnings -gt 0) {
    Log "DEPLOYMENT FREIGEGEBEN (mit $Warnings Warnungen)"
    exit 0
} else {
    Log "DEPLOYMENT FREIGEGEBEN"
    exit 0
}
