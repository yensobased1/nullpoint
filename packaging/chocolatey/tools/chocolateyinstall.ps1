$ErrorActionPreference = 'Stop'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$url = 'https://github.com/yensobased1/nullpoint/releases/download/v2.2.4/Nullpoint.exe'
$checksum = 'bfae40d36ec2389df5ee96d9f1ec91d9c4bff8a0278bbcd35164db85cd56dc4c'

# Portable exe: downloaded and checked against the SHA-256 above, then shimmed as a GUI app.
Get-ChocolateyWebFile -PackageName 'nullpoint' -FileFullPath (Join-Path $toolsDir 'Nullpoint.exe') `
  -Url64bit $url -Checksum64 $checksum -ChecksumType64 'sha256'
New-Item -ItemType File -Force -Path (Join-Path $toolsDir 'Nullpoint.exe.gui') | Out-Null
