# Prepare a seven-day loopback-only HTTPS certificate. Does not trust or install it.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$certFolder = Join-Path (Get-Location).Path 'data/local/devtls'
New-Item -ItemType Directory -Path $certFolder -Force | Out-Null
if (Test-Path -LiteralPath (Join-Path $certFolder 'key.pem')) {
    throw 'A local key already exists. Inspect its certificate before replacing it.'
}
$rsaKey = [System.Security.Cryptography.RSA]::Create(2048)
$certRequest = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
    'CN=People Quality Loopback Development', $rsaKey,
    [System.Security.Cryptography.HashAlgorithmName]::SHA256,
    [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
)
$sanBuilder = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
$sanBuilder.AddDnsName('localhost')
$sanBuilder.AddIpAddress([System.Net.IPAddress]::Parse('127.0.0.1'))
$certRequest.CertificateExtensions.Add($sanBuilder.Build())
$certRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false, $false, 0, $true)
)
$usageFlags = [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor
    [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment
$certRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new($usageFlags, $true)
)
$oidList = [System.Security.Cryptography.OidCollection]::new()
$oidList.Add([System.Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.1')) | Out-Null
$certRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($oidList, $true)
)
$localCert = $certRequest.CreateSelfSigned([DateTimeOffset]::UtcNow.AddMinutes(-5), [DateTimeOffset]::UtcNow.AddDays(7))
[System.IO.File]::WriteAllText((Join-Path $certFolder 'key.pem'), $rsaKey.ExportPkcs8PrivateKeyPem())
[System.IO.File]::WriteAllText((Join-Path $certFolder 'cert.pem'), $localCert.ExportCertificatePem())
[System.IO.File]::WriteAllBytes((Join-Path $certFolder 'cert.cer'), $localCert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
$certInfo = @{thumbprint=$localCert.Thumbprint;expires=$localCert.NotAfter.ToUniversalTime().ToString('o');trusted=$false;purpose='Loopback HTTPS OAuth callback only'}
$certInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $certFolder 'info.json')
$localCert.Dispose()
$rsaKey.Dispose()
Write-Output 'Prepared local HTTPS certificate. It has NOT been trusted or installed.'
