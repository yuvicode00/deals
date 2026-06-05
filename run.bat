@echo off
cd /d %~dp0
if not exist .venv ( echo Setting up (first run)... & python -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if "%ANTHROPIC_API_KEY%"=="" echo !! No ANTHROPIC_API_KEY - auto-read off; manual entry still works.
echo.
echo   Deal Studio:  open  http://localhost:8000   (Ctrl+C to stop)
python -m uvicorn app:app --host 127.0.0.1 --port 8000
