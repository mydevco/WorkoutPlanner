param(
    [switch]$ResetVenv
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$AlreadyActive = $env:VIRTUAL_ENV

foreach ($RequiredFile in @("requirements.txt", "run_windows.py", "forge_fitness.spec")) {
    if (-not (Test-Path (Join-Path $ProjectRoot $RequiredFile))) {
        throw "This is not the Forge Fitness source folder: '$ProjectRoot' is missing $RequiredFile. Clone or check out the project branch, then run this script from its repository root."
    }
}

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
if ($AlreadyActive -eq $VenvPath -or $AlreadyActive -eq (Resolve-Path $VenvPath -ErrorAction SilentlyContinue).Path) {
    Write-Host "Setup complete. The project environment is already active; do not run Activate.ps1 again."
} elseif ($AlreadyActive) {
    Write-Host "Setup complete. Another virtual environment is active ($AlreadyActive); open a new shell before activating this one."
} else {
    Write-Host "Setup complete. Activate once with .\.venv\Scripts\Activate.ps1"
}
