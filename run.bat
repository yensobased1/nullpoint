@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (echo Run setup.bat first. & pause & exit /b 1)
call .venv\Scripts\activate.bat
start "" pythonw crosshair\main.py
