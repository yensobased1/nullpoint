$ErrorActionPreference = 'Stop'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$url = 'https://github.com/yensobased1/nullpoint/releases/download/v2.2.1/Nullpoint.exe'
$checksum = '9c7b116409e6154dcb632cbb04b46de9a619b6eb583549513a0c330467784121'

# Portable exe: downloaded and checked against the SHA-256 above, then shimmed as a GUI app.
Get-ChocolateyWebFile -PackageName 'nullpoint' -FileFullPath (Join-Path $toolsDir 'Nullpoint.exe') `
  -Url64bit $url -Checksum64 $checksum -ChecksumType64 'sha256'
New-Item -ItemType File -Force -Path (Join-Path $toolsDir 'Nullpoint.exe.gui') | Out-Null
