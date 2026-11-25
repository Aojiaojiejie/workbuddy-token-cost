@echo off
rem Double-click wrapper for uninstall.ps1. Extra arguments are forwarded.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
