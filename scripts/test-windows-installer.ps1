[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\SecretBase"
$DataRoot = Join-Path $env:LOCALAPPDATA "SecretBase"
$Installer = (Resolve-Path $InstallerPath).Path

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string]$Arguments = "",
        [string]$WorkingDirectory = $env:TEMP
    )
    $Process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -Wait `
        -PassThru
    if ($Process.ExitCode -ne 0) {
        throw "$FilePath failed with exit code $($Process.ExitCode)."
    }
}

function Install-SecretBase {
    Invoke-CheckedProcess `
        -FilePath $Installer `
        -Arguments "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"
    $Executable = Join-Path $InstallDir "SecretBase.exe"
    if (-not (Test-Path $Executable)) {
        throw "SecretBase.exe was not installed."
    }
    return $Executable
}

function Uninstall-SecretBase {
    param([string]$ExtraArguments = "")
    $Uninstaller = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path $Uninstaller)) {
        throw "The SecretBase uninstaller was not found."
    }
    $Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART $ExtraArguments".Trim()
    Invoke-CheckedProcess -FilePath $Uninstaller -Arguments $Arguments -WorkingDirectory $env:TEMP
    Start-Sleep -Seconds 1
    if (Test-Path $InstallDir) {
        throw "The SecretBase installation directory remained after uninstall."
    }
}

if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
if (Test-Path $DataRoot) { Remove-Item -Recurse -Force $DataRoot }

$Executable = Install-SecretBase
$SelfTestData = Join-Path $DataRoot "installer-self-test"
$SelfTestReport = Join-Path $env:TEMP "secretbase-installer-self-test.json"
Invoke-CheckedProcess `
    -FilePath $Executable `
    -Arguments "--self-test --data-root `"$SelfTestData`" --report `"$SelfTestReport`""
$Result = Get-Content -Raw $SelfTestReport | ConvertFrom-Json
if (-not $Result.success -or -not $Result.frontend_loaded) {
    throw "The installed desktop self-test report is invalid."
}

New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
$PreserveSentinel = Join-Path $DataRoot "preserve-after-uninstall.txt"
Set-Content -LiteralPath $PreserveSentinel -Encoding Ascii -Value "preserve"
Uninstall-SecretBase
if (-not (Test-Path $PreserveSentinel)) {
    throw "Default uninstall removed SecretBase user data."
}

$Executable = Install-SecretBase
$PurgeSentinel = Join-Path $DataRoot "purge-after-confirmation.txt"
Set-Content -LiteralPath $PurgeSentinel -Encoding Ascii -Value "purge"
Uninstall-SecretBase -ExtraArguments "/PURGEDATA=1 /CONFIRMDELETE=DELETE"
if (Test-Path $DataRoot) {
    throw "Confirmed uninstall did not remove the SecretBase data directory."
}

if (Get-Process -Name "SecretBase" -ErrorAction SilentlyContinue) {
    throw "SecretBase process remained after installer tests."
}

Write-Host "PASS Windows installer install, preserve, and purge tests"
