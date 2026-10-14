@echo off
REM Start the CreditWise web app on http://127.0.0.1:8000
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else (set PY=python)
if not exist "model\artifacts\naive_bayes.joblib" (
  echo Model artifacts not found - exporting them from the notebook pipeline...
  %PY% model\export_model.py || goto :error
)
echo.
echo  CreditWise is starting at http://127.0.0.1:8000   (press Ctrl+C to stop)
echo.
start "" "http://127.0.0.1:8000"
%PY% -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
goto :eof
:error
echo Export failed. See the message above.
pause
