# build.ps1 — Build Windows d'ORAKLE (PyInstaller, onedir).
# Usage :  powershell -ExecutionPolicy Bypass -File .\build.ps1
# Sortie :  dist\ORAKLE\ORAKLE.exe
#
# NB : ne PAS rediriger la sortie d'exécutables natifs avec 2>&1 (piège
# PowerShell 5.1 : chaque ligne stderr devient une erreur même à exit 0).

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== ORAKLE build ===" -ForegroundColor Cyan

# 1. PyInstaller présent ?
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller absent - installation..." -ForegroundColor Yellow
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "Installation de PyInstaller impossible." }
}

# 2. Dependances coeur presentes ?
python -c "import PyQt6, faster_whisper, sounddevice, pynput, pyperclip, numpy"
if ($LASTEXITCODE -ne 0) { throw "Dependances manquantes - pip install -r requirements.txt" }

# 3. Build
python -m PyInstaller orakle.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "Build PyInstaller en echec." }

# 4. Verification de la sortie
$exe = Join-Path $PSScriptRoot "dist\ORAKLE\ORAKLE.exe"
if (-not (Test-Path $exe)) { throw "ORAKLE.exe introuvable dans dist\ORAKLE\" }

$size = [math]::Round((Get-ChildItem "dist\ORAKLE" -Recurse | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "=== OK : $exe (dossier ~$size Mo) ===" -ForegroundColor Green
Write-Host "Lancer :  dist\ORAKLE\ORAKLE.exe"
