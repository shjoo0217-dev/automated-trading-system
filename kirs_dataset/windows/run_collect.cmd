@echo off
setlocal
cd /d "%~dp0.."
set PYTHONUTF8=1
".venv\Scripts\python.exe" -X utf8 windows\run_job.py --root . --mode collect
exit /b %errorlevel%
