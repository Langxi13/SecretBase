[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path
)

$ErrorActionPreference = "Stop"
$CertificateBase64 = $env:WINDOWS_SIGNING_CERT_BASE64
$CertificatePassword = $env:WINDOWS_SIGNING_CERT_PASSWORD
$TimestampUrl = if ($env:WINDOWS_SIGNING_TIMESTAMP_URL) {
    $env:WINDOWS_SIGNING_TIMESTAMP_URL
} else {
    "http://timestamp.digicert.com"
}

if (-not $CertificateBase64 -and -not $CertificatePassword) {
    Write-Host "Windows signing certificate is not configured; artifacts remain unsigned."
    exit 0
}
if (-not $CertificateBase64 -or -not $CertificatePassword) {
    throw "Windows signing configuration is incomplete."
}

$SignTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter signtool.exe -Recurse |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $SignTool) {
    throw "signtool.exe was not found."
}

$TempRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$CertificatePath = Join-Path $TempRoot "secretbase-signing.pfx"
$ImportedCertificate = $null
try {
    [System.IO.File]::WriteAllBytes($CertificatePath, [Convert]::FromBase64String($CertificateBase64))
    $SecurePassword = ConvertTo-SecureString $CertificatePassword -AsPlainText -Force
    $ImportedCertificate = Import-PfxCertificate `
        -FilePath $CertificatePath `
        -CertStoreLocation Cert:\CurrentUser\My `
        -Password $SecurePassword
    if (-not $ImportedCertificate) {
        throw "The Windows signing certificate could not be imported."
    }

    foreach ($Target in $Path) {
        $ResolvedTarget = (Resolve-Path $Target).Path
        & $SignTool.FullName sign /sha1 $ImportedCertificate.Thumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $ResolvedTarget
        if ($LASTEXITCODE -ne 0) { throw "Failed to sign $ResolvedTarget" }
        & $SignTool.FullName verify /pa /v $ResolvedTarget
        if ($LASTEXITCODE -ne 0) { throw "Signature verification failed for $ResolvedTarget" }
    }
} finally {
    if ($ImportedCertificate) {
        Remove-Item "Cert:\CurrentUser\My\$($ImportedCertificate.Thumbprint)" -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $CertificatePath -Force -ErrorAction SilentlyContinue
}
