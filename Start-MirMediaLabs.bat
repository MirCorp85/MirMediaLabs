@echo off
:: MIR MEDIA LABS - start the server (if not running) and open the studio window.
:: Usage: Start-MirMediaLabs.bat [--server-only]
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not defined PYW set PYW=pythonw.exe
cd /d "%~dp0server"
powershell -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 5400 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -FilePath '%PYW%' -ArgumentList '-u','medialab.py' -WorkingDirectory '%~dp0server' -WindowStyle Hidden -RedirectStandardOutput '%~dp0data\logs\server_out.log' -RedirectStandardError '%~dp0data\logs\server_err.log' }"
if "%~1"=="--server-only" exit /b 0
timeout /t 2 /nobreak >nul
set CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe
if exist "%CHROME%" (
  start "" "%CHROME%" --app=http://127.0.0.1:5400/ --window-size=1500,950
) else (
  start "" http://127.0.0.1:5400/
)
