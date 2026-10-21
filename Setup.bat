@echo off
:: MIR MEDIA LABS - setup wizard for a cloned repository (Windows + NVIDIA GPU).
:: Installs everything inside this folder: runtime\ (Python + PyTorch), engine\ (ComfyUI + models).
:: Usage: Setup.bat [--yes] [--components image,ace] [--engine none] [--help]
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "UV=%~dp0runtime\uv.exe"
set "UV_PYTHON_INSTALL_DIR=%~dp0runtime\python"
set "UV_CACHE_DIR=%~dp0runtime\cache"
if exist "%UV%" goto run
echo Getting uv (a small Python installer from astral.sh) ...
if not exist "%~dp0runtime" mkdir "%~dp0runtime"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $t=Join-Path $env:TEMP 'mml-uv'; Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue; Invoke-WebRequest -UseBasicParsing 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile ($t + '.zip'); Expand-Archive -Force ($t + '.zip') $t; Copy-Item (Get-ChildItem $t -Recurse -Filter uv.exe | Select-Object -First 1).FullName $env:UV"
if not exist "%UV%" (
  echo Could not download uv. Check your internet connection and run Setup.bat again.
  pause
  exit /b 1
)
:run
"%UV%" run --no-project --python 3.13 --managed-python "%~dp0installer\source_setup.py" %*
set RC=%ERRORLEVEL%
if "%~1"=="" pause
exit /b %RC%
