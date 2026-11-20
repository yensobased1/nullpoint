@echo off
rem Authenticode-sign one file with Azure Trusted Signing (see docs\SIGNING.md).
rem Skipped cleanly (exit 0) when signing isn't set up. Usage: sign.bat path\to\file.exe
if "%NULLPOINT_SIGN_DLIB%"=="" (echo Code signing not configured: skipped for %~nx1. & exit /b 0)
if "%NULLPOINT_SIGN_METADATA%"=="" (echo NULLPOINT_SIGN_METADATA is not set: see docs\SIGNING.md & exit /b 1)
set "SIGNTOOL="
for /f "delims=" %%S in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*signtool.exe" 2^>nul ^| findstr /i "\\x64\\"') do set "SIGNTOOL=%%S"
if "%SIGNTOOL%"=="" (echo signtool.exe not found: install the Windows SDK, see docs\SIGNING.md & exit /b 1)
"%SIGNTOOL%" sign /v /fd SHA256 /tr "http://timestamp.acs.microsoft.com" /td SHA256 ^
  /dlib "%NULLPOINT_SIGN_DLIB%" /dmdf "%NULLPOINT_SIGN_METADATA%" "%~1" || exit /b 1
"%SIGNTOOL%" verify /pa "%~1" || exit /b 1
