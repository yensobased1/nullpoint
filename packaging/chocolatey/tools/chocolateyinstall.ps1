$ErrorActionPreference = 'Stop'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$url = 'https://github.com/yensobased1/nullpoint/releases/download/v2.2.0/Nullpoint.exe'
$checksum = '6252eaf061fc08b4908a3fa17d4fda899e45737c74b4e2be5ac020f6a4910973'

# Portable exe: downloaded and checked against the SHA-256 above, then shimmed as a GUI app.
Get-ChocolateyWebFile -PackageName 'nullpoint' -FileFullPath (Join-Path $toolsDir 'Nullpoint.exe') `
  -Url64bit $url -Checksum64 $checksum -ChecksumType64 'sha256'
New-Item -ItemType File -Force -Path (Join-Path $toolsDir 'Nullpoint.exe.gui') | Out-Null
