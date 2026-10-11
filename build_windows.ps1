$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "The project virtual environment is missing. Run .\setup_windows.ps1 first."
}

& $VenvPython -m PyInstaller --noconfirm --clean forge_fitness.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
Write-Host "Build complete: $ProjectRoot\dist\ForgeFitness.exe"
