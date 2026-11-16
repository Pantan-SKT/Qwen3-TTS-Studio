@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Qwen3-TTS CUDA Repair
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing Python environment. Run start.bat first.
  if not "%~1"=="/quiet" pause
  exit /b 1
)
echo [Repair] Installing official PyTorch 2.9.1 CUDA 12.8 wheels...
echo [Repair] This is a large download. Your other Python installations are not changed.
".venv\Scripts\python.exe" -m pip install --upgrade --force-reinstall torch==2.9.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (
  echo [ERROR] CUDA PyTorch installation failed.
  if not "%~1"=="/quiet" pause
  exit /b 1
)
echo [Repair] Testing CUDA availability...
".venv\Scripts\python.exe" -m app.cuda_check
if errorlevel 1 (
  echo [ERROR] CUDA is still unavailable. Run cuda-diagnostics.bat.
  if not "%~1"=="/quiet" pause
  exit /b 1
)
echo [OK] CUDA ready! Restart start.bat.
if not "%~1"=="/quiet" pause
exit /b 0
