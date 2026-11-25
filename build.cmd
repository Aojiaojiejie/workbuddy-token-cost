@echo off
rem Wrapper that bypasses execution policy for build.ps1. Extra arguments are forwarded.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
