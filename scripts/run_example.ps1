$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "..")
try {
    & ".\.venv\Scripts\python.exe" -m auto_analyse --demo @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & ".\.venv\Scripts\python.exe" -m auto_analyse.brand --demo @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
