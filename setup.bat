@echo off
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python 3.11+ not found. Install it from python.org and tick "Add to PATH". & pause & exit /b 1)
python -m venv .venv || (pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
rem Exact versions + hashes: pip refuses any package that doesn't match (no surprise upgrades, no tampered files).
pip install --require-hashes -r requirements.txt || (pause & exit /b 1)
echo.
echo Setup done. Start the overlay with run.bat
pause
