@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)
call .venv\Scripts\activate.bat
pip install pyinstaller || (pause & exit /b 1)
pyinstaller --noconfirm --onefile --noconsole --name Nullpoint --icon assets\nullpoint.ico ^
  --add-data "crosshair\lang;lang" --add-data "assets;assets" crosshair\main.py
echo.
echo Built dist\Nullpoint.exe
pause
