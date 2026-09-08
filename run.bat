@echo off
REM PSK Game Recommender - one-click demo.
REM Starts the API and opens the personalised lobby in your browser.
REM No FEG source CSVs are needed: the trained model ships in artifacts\.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH. Install Python 3.10+ and try again.
  pause
  exit /b 1
)

if not exist "artifacts\model.npz" (
  echo Missing artifacts\model.npz
  echo Run:  python -m src.cli build --data-dir ^<folder with the FEG CSVs^>
  pause
  exit /b 1
)

echo Starting the PSK recommender. Ctrl-C to stop.
echo   lobby    http://127.0.0.1:8000/
echo   backend  http://127.0.0.1:8000/backend
python -m src.cli demo
pause
