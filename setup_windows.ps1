param(
    [switch]$ResetVenv
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$VenvPath = Join-Path $ProjectRoot ".venv"

if ($ResetVenv) {
    if (Test-Path $VenvPath) {
        Write-Host "Removing only $VenvPath"
        Remove-Item -LiteralPath $VenvPath -Recurse -Force
    }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and
    -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.12 or 3.13 and reopen PowerShell."
}

$PythonArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($Candidate in @("3.13", "3.12")) {
        & py "-$Candidate" --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $PythonArgs = @("-$Candidate")
            break
        }
    }
}

function Invoke-Python([string[]]$Arguments) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py @PythonArgs @Arguments
    } else {
        & python @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path (Join-Path $VenvPath "Scripts\python.exe"))) {
    Write-Host "Creating $VenvPath"
    Invoke-Python @("-m", "venv", ".venv")
}

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
Write-Host "Setup complete. Activate with .\.venv\Scripts\Activate.ps1"
