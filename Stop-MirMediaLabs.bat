@echo off
:: Stop the MIR MEDIA LABS server (only the process listening on :5400 - never MirOS or ComfyUI).
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5400 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
echo MIR MEDIA LABS stopped.
