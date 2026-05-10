$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "Starting SecretBase frontend on http://127.0.0.1:8000"
python -m http.server 8000 -d $FrontendDir
