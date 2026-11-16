@echo off
cd /d "%~dp0"
echo === NVIDIA GPU ===
nvidia-smi
echo.
echo === Python and PyTorch CUDA ===
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m app.cuda_check
  ".venv\Scripts\python.exe" -m pip show torch torchaudio
) else (
  echo Virtual environment not found.
)
pause
