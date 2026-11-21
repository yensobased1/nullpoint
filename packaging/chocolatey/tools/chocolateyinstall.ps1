$ErrorActionPreference = 'Stop'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$url = 'https://github.com/yensobased1/nullpoint/releases/download/v2.2.3/Nullpoint.exe'
$checksum = '8a720342a0a3a8603a8f984e6d5e7cc4938b217d8353c7c7ade74360388e2e56'

# Portable exe: downloaded and checked against the SHA-256 above, then shimmed as a GUI app.
Get-ChocolateyWebFile -PackageName 'nullpoint' -FileFullPath (Join-Path $toolsDir 'Nullpoint.exe') `
  -Url64bit $url -Checksum64 $checksum -ChecksumType64 'sha256'
New-Item -ItemType File -Force -Path (Join-Path $toolsDir 'Nullpoint.exe.gui') | Out-Null
