$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$VenvPath = Join-Path $ProjectRoot ".venv-build-win"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$DistPath = Join-Path $ProjectRoot "dist\windows"
$WorkPath = Join-Path $ProjectRoot "build\pyinstaller"
$SpecPath = Join-Path $ProjectRoot "build\pyinstaller-spec"

if (-not (Test-Path $PythonExe)) {
    py -3 -m venv $VenvPath
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install --upgrade ".[build]"

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name wordflow `
    --paths src `
    --collect-all textual `
    --collect-all rich `
    --distpath $DistPath `
    --workpath $WorkPath `
    --specpath $SpecPath `
    tools\wordflow_launcher.py

Write-Host ""
Write-Host "Built: $DistPath\wordflow.exe"
