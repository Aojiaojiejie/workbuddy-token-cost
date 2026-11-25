@echo off
rem Development launcher: run the GUI from source (not the packaged exe).
rem Requires: python -m pip install -r requirements.txt
setlocal
pushd "%~dp0.."
python gui_app.py %*
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" pause
exit /b %RC%
