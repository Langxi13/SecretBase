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

& $BootstrapCommand.Source -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and sys.maxsize > 2**32 else 1)"
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
$RuntimeSelfTestReport = Join-Path $BuildRoot "runtime-self-test-report.json"
$PackageDir = Join-Path $DistRoot "SecretBase"
$ArtifactsDir = Join-Path $ProjectRoot "artifacts"
$ArchiveName = "SecretBase-v$Version-windows-x64.zip"
$ArchivePath = Join-Path $ArtifactsDir $ArchiveName
$InstallerName = "SecretBase-v$Version-windows-x64-setup.exe"
$InstallerPath = Join-Path $ArtifactsDir $InstallerName
$ChecksumPath = Join-Path $ArtifactsDir "SHA256SUMS.txt"
$InstallerScript = Join-Path $ProjectRoot "desktop\installer\SecretBase.iss"
$InstallerLanguage = Join-Path $ProjectRoot "desktop\installer\languages\ChineseSimplified.isl"
$GeneratedInstallerScript = Join-Path $BuildRoot "SecretBase.generated.iss"
$GeneratedInstallerLanguage = Join-Path $BuildRoot "ChineseSimplified.isl"
$SigningScript = Join-Path $ProjectRoot "scripts\sign-windows-artifacts.ps1"

foreach ($Path in @($DistRoot, $WorkRoot, $SelfTestRoot, $SelfTestReport, $RuntimeSelfTestReport, $ArchivePath, $InstallerPath, $ChecksumPath, $GeneratedInstallerScript, $GeneratedInstallerLanguage)) {
    if (Test-Path $Path) { Remove-Item -Recurse -Force $Path }
}
New-Item -ItemType Directory -Force -Path $DistRoot, $WorkRoot, $ArtifactsDir | Out-Null

Push-Location $ProjectRoot
try {
    & $BuildPython -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $WorkRoot "desktop\SecretBase.spec"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

    Copy-Item (Join-Path $ProjectRoot "LICENSE") (Join-Path $PackageDir "LICENSE.txt")
    Copy-Item (Join-Path $ProjectRoot "desktop\SecretBase.exe.config") (Join-Path $PackageDir "SecretBase.exe.config")

    $Executable = Join-Path $PackageDir "SecretBase.exe"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SigningScript -Path $Executable
    if ($LASTEXITCODE -ne 0) { throw "Signing the desktop executable failed." }

    & $BuildPython "scripts\verify_desktop_package.py" $PackageDir
    if ($LASTEXITCODE -ne 0) { throw "The unpacked desktop package failed validation." }

    $SelfTestArguments = "--self-test --data-root self-test-data --report self-test-report.json"
    $SelfTestProcess = Start-Process -FilePath $Executable -ArgumentList $SelfTestArguments -WorkingDirectory $BuildRoot -Wait -PassThru
    if ($SelfTestProcess.ExitCode -ne 0) {
        $SelfTestLog = Join-Path $SelfTestRoot "logs\secretbase.log"
        if (Test-Path $SelfTestReport) { Get-Content -Raw $SelfTestReport | Write-Host }
        if (Test-Path $SelfTestLog) { Get-Content -Tail 100 $SelfTestLog | Write-Host }
        throw "The packaged desktop self-test failed with exit code $($SelfTestProcess.ExitCode)."
    }
    $SelfTest = Get-Content -Raw $SelfTestReport | ConvertFrom-Json
    if (-not $SelfTest.success -or -not $SelfTest.frontend_loaded) {
        throw "The packaged desktop self-test report is invalid."
    }

    $RuntimeSelfTestArguments = "--desktop-runtime-self-test --report runtime-self-test-report.json"
    $RuntimeSelfTestProcess = Start-Process -FilePath $Executable -ArgumentList $RuntimeSelfTestArguments -WorkingDirectory $BuildRoot -Wait -PassThru
    if ($RuntimeSelfTestProcess.ExitCode -ne 0) {
        if (Test-Path $RuntimeSelfTestReport) { Get-Content -Raw $RuntimeSelfTestReport | Write-Host }
        throw "The packaged desktop runtime self-test failed with exit code $($RuntimeSelfTestProcess.ExitCode)."
    }
    $RuntimeSelfTest = Get-Content -Raw $RuntimeSelfTestReport | ConvertFrom-Json
    if (-not $RuntimeSelfTest.success -or $RuntimeSelfTest.renderer -ne "edgechromium") {
        throw "The packaged desktop runtime self-test report is invalid."
    }

    Compress-Archive -Path $PackageDir -DestinationPath $ArchivePath -CompressionLevel Optimal
    & $BuildPython "scripts\verify_desktop_package.py" $ArchivePath
    if ($LASTEXITCODE -ne 0) { throw "The desktop ZIP archive failed validation." }

    $IsccCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    $IsccPath = if ($IsccCommand) {
        $IsccCommand.Source
    } else {
        Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    }
    if (-not (Test-Path $IsccPath)) {
        throw "Inno Setup 6.7.1 was not found. Install it before building the Windows installer."
    }

    $InstallerSource = [System.IO.File]::ReadAllText($InstallerScript, [System.Text.Encoding]::UTF8)
    $LanguageSource = [System.IO.File]::ReadAllText($InstallerLanguage, [System.Text.Encoding]::UTF8)
    [System.IO.File]::WriteAllText($GeneratedInstallerScript, $InstallerSource, [System.Text.UTF8Encoding]::new($true))
    [System.IO.File]::WriteAllText($GeneratedInstallerLanguage, $LanguageSource, [System.Text.UTF8Encoding]::new($true))
    & $IsccPath `
        "/DMyAppVersion=$Version" `
        "/DMySourceDir=$PackageDir" `
        "/DMyOutputDir=$ArtifactsDir" `
        "/DMyProjectRoot=$ProjectRoot" `
        "/DMyLanguageFile=$GeneratedInstallerLanguage" `
        $GeneratedInstallerScript
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $InstallerPath)) {
        throw "Inno Setup failed to build the Windows installer."
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SigningScript -Path $InstallerPath
    if ($LASTEXITCODE -ne 0) { throw "Signing the Windows installer failed." }

    $ArchiveHash = (Get-FileHash -Algorithm SHA256 $ArchivePath).Hash.ToLowerInvariant()
    $InstallerHash = (Get-FileHash -Algorithm SHA256 $InstallerPath).Hash.ToLowerInvariant()
    $Checksum = "$ArchiveHash  $ArchiveName`r`n$InstallerHash  $InstallerName`r`n"
    [System.IO.File]::WriteAllText($ChecksumPath, $Checksum, [System.Text.UTF8Encoding]::new($false))
} finally {
    Pop-Location
}

Write-Host "Desktop package: $ArchivePath"
Write-Host "Desktop installer: $InstallerPath"
Write-Host "Checksums: $ChecksumPath"
