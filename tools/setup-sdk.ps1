$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $root 'local/toolchain'
$lock = Get-Content -LiteralPath "$PSScriptRoot/sdk-lock.json" -Raw | ConvertFrom-Json
$archive = Join-Path $tools ("rexglue-sdk-" + $lock.build + '-win-amd64.zip')
$destination = Join-Path $tools ("rexglue-" + $lock.build)
$sdk = Join-Path $destination 'win-amd64'
New-Item -ItemType Directory -Path $tools -Force | Out-Null
if (Test-Path -LiteralPath $sdk) {
    & "$PSScriptRoot/verify-sdk.ps1" -Sdk $sdk
    return
}
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest -UseBasicParsing $lock.url -OutFile $archive
}
$expected = $lock.archive_sha256
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'SDK archive checksum mismatch'
}
Expand-Archive -LiteralPath $archive -DestinationPath $destination
& "$PSScriptRoot/verify-sdk.ps1" -Sdk $sdk
