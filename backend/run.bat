@echo off
cd /d "%~dp0"
set PYTHONPATH=.
if not exist ".venv\Scripts\uvicorn.exe" (
  echo Virtual env missing. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
.venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8000
