@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0patch-thai.exe" (
  echo patch-thai.exe was not found next to this file.
  pause
  exit /b 1
)
"%~dp0patch-thai.exe"
echo.
pause
