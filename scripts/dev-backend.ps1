$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectRoot "backend"

Write-Host "Starting SecretBase backend on http://127.0.0.1:10004"
Push-Location $BackendDir
try {
    uvicorn main:app --host 127.0.0.1 --port 10004
}
finally {
    Pop-Location
}
