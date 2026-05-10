$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectRoot "backend"

Write-Host "Starting SecretBase backend on http://127.0.0.1:10004"
if (-not $env:DEEPSEEK_API_KEY) {
    $DeepSeekKey = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User")
    if (-not $DeepSeekKey) {
        $DeepSeekKey = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Machine")
    }
    if ($DeepSeekKey) {
        $env:DEEPSEEK_API_KEY = $DeepSeekKey
        Write-Host "Loaded DEEPSEEK_API_KEY from Windows environment"
    }
}
Push-Location $BackendDir
try {
    uvicorn main:app --host 127.0.0.1 --port 10004
}
finally {
    Pop-Location
}
