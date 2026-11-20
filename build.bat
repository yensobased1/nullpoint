@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)
call .venv\Scripts\activate.bat
pip install --require-hashes -r requirements.txt -r requirements-dev.txt || (pause & exit /b 1)
pyinstaller --noconfirm --onefile --noconsole --name Nullpoint --icon assets\nullpoint.ico ^
  --add-data "crosshair\lang;lang" --add-data "assets;assets" --add-data "CHANGELOG.md;." crosshair\main.py
echo.
echo Built dist\Nullpoint.exe
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  "%ISCC%" installer\nullpoint.iss
) else (
  echo Inno Setup not found, skipping the installer. Install it with: winget install JRSoftware.InnoSetup
)
pause
