$ErrorActionPreference = 'Stop'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$url = 'https://github.com/yensobased1/nullpoint/releases/download/v2.2.2/Nullpoint.exe'
$checksum = 'fd71aca821cabbcfdede87c43c70e10198f71f7f10e72f49cd27e3e507d2390a'

# Portable exe: downloaded and checked against the SHA-256 above, then shimmed as a GUI app.
Get-ChocolateyWebFile -PackageName 'nullpoint' -FileFullPath (Join-Path $toolsDir 'Nullpoint.exe') `
  -Url64bit $url -Checksum64 $checksum -ChecksumType64 'sha256'
New-Item -ItemType File -Force -Path (Join-Path $toolsDir 'Nullpoint.exe.gui') | Out-Null
