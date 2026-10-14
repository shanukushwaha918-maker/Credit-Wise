@echo off
REM One-time setup: create a virtual environment and install dependencies.
cd /d "%~dp0"
python -m venv .venv || goto :error
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
echo.
echo Setup complete. Start the app with:  run.bat
goto :eof
:error
echo Setup failed. Make sure Python 3.11+ is installed and on PATH.
pause
