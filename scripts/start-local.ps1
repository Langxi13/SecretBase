param(
    [switch]$NoBrowser,
    [switch]$DryRun,
    [string]$DataRoot
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "backend\requirements.txt"
$StampFile = Join-Path $VenvDir ".secretbase-requirements.sha256"

$BootstrapCommand = Get-Command py -ErrorAction SilentlyContinue
$BootstrapArgs = @("-3")
if (-not $BootstrapCommand) {
    $BootstrapCommand = Get-Command python -ErrorAction SilentlyContinue
    $BootstrapArgs = @()
}
if (-not $BootstrapCommand) {
    throw "未找到 Python 3，请先安装 Python 3.10 或更高版本。"
}

& $BootstrapCommand.Source @BootstrapArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "SecretBase 需要 Python 3.10 或更高版本。"
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "正在创建本地虚拟环境..."
    & $BootstrapCommand.Source @BootstrapArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "创建虚拟环境失败。"
    }
}

$RequirementsHash = (Get-FileHash -Algorithm SHA256 $Requirements).Hash.ToLowerInvariant()
$InstalledHash = if (Test-Path $StampFile) { (Get-Content -Raw $StampFile).Trim() } else { "" }
if ($RequirementsHash -ne $InstalledHash) {
    Write-Host "正在安装或更新 SecretBase 依赖..."
    & $VenvPython -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "更新 pip 失败。" }
    & $VenvPython -m pip install --disable-pip-version-check -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "安装依赖失败。" }
    Set-Content -Path $StampFile -Value $RequirementsHash -NoNewline -Encoding ascii
}

$LauncherArgs = @()
if ($NoBrowser) { $LauncherArgs += "--no-browser" }
if ($DryRun) { $LauncherArgs += "--dry-run" }
if ($DataRoot) { $LauncherArgs += @("--data-root", $DataRoot) }

& $VenvPython (Join-Path $ProjectRoot "desktop\launcher.py") @LauncherArgs
exit $LASTEXITCODE
