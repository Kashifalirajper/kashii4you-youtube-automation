param(
    [switch]$Docker,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($Docker) {
    docker compose build
    if ($DryRun) {
        docker compose run --rm shorts-automation python automation.py run-once --region US --mode local --max-uploads 1 --dry-run
    } else {
        docker compose run --rm shorts-automation python automation.py deploy-run --region US --mode local --max-uploads 1
    }
    exit $LASTEXITCODE
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($DryRun) {
    & ".\.venv\Scripts\python.exe" automation.py run-once --region US --mode local --max-uploads 1 --dry-run
} else {
    & ".\.venv\Scripts\python.exe" automation.py deploy-run --region US --mode local --max-uploads 1
}
exit $LASTEXITCODE
