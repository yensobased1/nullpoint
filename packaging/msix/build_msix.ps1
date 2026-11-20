# Build dist\Nullpoint-<version>.msix from dist\Nullpoint.exe (run build.bat first). Needs makeappx.exe from the
# Windows SDK (winget install Microsoft.WindowsSDK.10.0.22621). Does not sign or submit anything: see docs\STORE.md.
param([Parameter(Mandatory)][string]$Version, [string]$Publisher = "")
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$layout = Join-Path $root "build\msix"
Remove-Item -Recurse -Force $layout -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$layout\Assets" | Out-Null
Copy-Item "$root\dist\Nullpoint.exe" $layout

# Store logos from the app icon (same artwork, the sizes the manifest asks for).
& "$root\.venv\Scripts\python.exe" -c @"
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtCore import Qt
app = QGuiApplication([])
src = QImage(r'$root\assets\nullpoint_256.png')
for name, w, h in (('Square44x44Logo', 44, 44), ('Square150x150Logo', 150, 150), ('StoreLogo', 50, 50), ('Wide310x150Logo', 310, 150)):
    img = QImage(w, h, QImage.Format_ARGB32); img.fill(0)
    s = min(w, h); icon = src.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p = QPainter(img); p.drawImage((w - s) // 2, (h - s) // 2, icon); p.end()
    img.save(rf'$layout\Assets\{name}.png')
"@

$manifest = Get-Content "$PSScriptRoot\AppxManifest.xml" -Raw
$manifest = $manifest -replace 'Version="\d+\.\d+\.\d+\.\d+"', "Version=`"$Version.0`""
if ($Publisher) { $manifest = $manifest.Replace("CN=REPLACE_WITH_PUBLISHER", $Publisher) }
Set-Content "$layout\AppxManifest.xml" $manifest -Encoding utf8

$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter makeappx.exe -ErrorAction SilentlyContinue |
    Where-Object FullName -match "\\x64\\" | Select-Object -Last 1
if (-not $makeappx) { Write-Host "makeappx.exe not found: install the Windows SDK. Layout is ready in $layout"; exit 1 }
& $makeappx.FullName pack /o /d $layout /p "$root\dist\Nullpoint-$Version.msix"
Write-Host "Built dist\Nullpoint-$Version.msix (unsigned: the Store signs it, or sign it yourself for sideloading)"
