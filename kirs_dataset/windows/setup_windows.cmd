@echo off
setlocal
cd /d "%~dp0.."
set PYTHONUTF8=1
py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -X utf8 -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -X utf8 -m pip install -e . --no-deps
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -X utf8 -m investment.cli verify --root .
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -X utf8 -m investment.cli validate --root .
exit /b %errorlevel%
