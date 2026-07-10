[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PIP_PROGRESS_BAR = "off"

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
    throw "The Windows desktop package must be built on Windows."
}

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BootstrapCommand = Get-Command $PythonCommand -ErrorAction SilentlyContinue
if (-not $BootstrapCommand) {
    throw "Python 3.11 x64 was not found."
}

& $BootstrapCommand.Source -c 'import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and struct.calcsize("P") == 8 else 1)'
if ($LASTEXITCODE -ne 0) {
    throw "SecretBase desktop builds require Python 3.11 x64."
}

$BuildEnvironment = Join-Path $ProjectRoot ".desktop-build\venv"
$BuildPython = Join-Path $BuildEnvironment "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "desktop\requirements.txt"

if ($SkipDependencyInstall) {
    $BuildPython = $BootstrapCommand.Source
    & $BuildPython -c 'import PyInstaller, webview'
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop build dependencies are not installed."
    }
} else {
    if (-not (Test-Path $BuildPython)) {
        & $BootstrapCommand.Source -m venv $BuildEnvironment
        if ($LASTEXITCODE -ne 0) { throw "Failed to create the desktop build environment." }
    }
    & $BuildPython -m pip install --disable-pip-version-check --progress-bar off --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to update pip." }
    & $BuildPython -m pip install --disable-pip-version-check --progress-bar off -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "Failed to install desktop build dependencies." }
}

$VersionSource = [System.IO.File]::ReadAllText((Join-Path $ProjectRoot "backend\version.py"))
$VersionMatch = [regex]::Match($VersionSource, 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $VersionMatch.Success) {
    throw "Unable to read APP_VERSION."
}
$Version = $VersionMatch.Groups[1].Value

$BuildRoot = Join-Path $ProjectRoot "build\desktop-windows"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$SelfTestRoot = Join-Path $BuildRoot "self-test-data"
$SelfTestReport = Join-Path $BuildRoot "self-test-report.json"
$PackageDir = Join-Path $DistRoot "SecretBase"
$ArtifactsDir = Join-Path $ProjectRoot "artifacts"
$ArchiveName = "SecretBase-v$Version-windows-x64.zip"
$ArchivePath = Join-Path $ArtifactsDir $ArchiveName
$ChecksumPath = Join-Path $ArtifactsDir "SHA256SUMS.txt"

foreach ($Path in @($DistRoot, $WorkRoot, $SelfTestRoot, $SelfTestReport, $ArchivePath, $ChecksumPath)) {
    if (Test-Path $Path) { Remove-Item -Recurse -Force $Path }
}
New-Item -ItemType Directory -Force -Path $DistRoot, $WorkRoot, $ArtifactsDir | Out-Null

Push-Location $ProjectRoot
try {
    & $BuildPython -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $WorkRoot "desktop\SecretBase.spec"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

    Copy-Item (Join-Path $ProjectRoot "LICENSE") (Join-Path $PackageDir "LICENSE.txt")
    & $BuildPython "scripts\verify_desktop_package.py" $PackageDir
    if ($LASTEXITCODE -ne 0) { throw "The unpacked desktop package failed validation." }

    $Executable = Join-Path $PackageDir "SecretBase.exe"
    & $Executable --self-test --data-root $SelfTestRoot --report $SelfTestReport
    if ($LASTEXITCODE -ne 0) { throw "The packaged desktop self-test failed." }
    $SelfTest = Get-Content -Raw $SelfTestReport | ConvertFrom-Json
    if (-not $SelfTest.success -or -not $SelfTest.frontend_loaded) {
        throw "The packaged desktop self-test report is invalid."
    }

    Compress-Archive -Path $PackageDir -DestinationPath $ArchivePath -CompressionLevel Optimal
    & $BuildPython "scripts\verify_desktop_package.py" $ArchivePath
    if ($LASTEXITCODE -ne 0) { throw "The desktop ZIP archive failed validation." }

    $Hash = (Get-FileHash -Algorithm SHA256 $ArchivePath).Hash.ToLowerInvariant()
    $Checksum = "$Hash  $ArchiveName`r`n"
    [System.IO.File]::WriteAllText($ChecksumPath, $Checksum, [System.Text.UTF8Encoding]::new($false))
} finally {
    Pop-Location
}

Write-Host "Desktop package: $ArchivePath"
Write-Host "Checksums: $ChecksumPath"
