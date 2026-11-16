@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Qwen3-TTS Studio

if exist ".venv\Scripts\python.exe" goto verify_venv

echo [Setup] Checking Python 3.12 (64-bit)...
call :find_python
if defined PYTHON_EXE goto create_venv

echo.
echo [ERROR] Python 3.12 (64-bit) was not found.
echo Python 3.13 or older Python versions are not used automatically.
echo.
where winget >nul 2>&1
if errorlevel 1 goto manual_python
choice /C JN /N /M "Install Python 3.12 automatically via winget? [J/N] "
if errorlevel 2 goto manual_python

echo [Setup] Installing Python 3.12...
winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo [ERROR] Python installation was unsuccessful.
  goto manual_python
)
call :find_python
if defined PYTHON_EXE goto create_venv
echo [INFO] Python may be installed, but is not yet visible to this terminal.
echo Close this window, open a NEW terminal, and run start.bat again.
pause
exit /b 1

:manual_python
echo.
echo Install Python 3.12 (64-bit) from https://www.python.org/downloads/
echo or run in PowerShell: winget install --id Python.Python.3.12 -e
echo After installation, start this script again.
pause
exit /b 1

:find_python
set "PYTHON_EXE="
set "PYTHON_ARGS="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.12 -c "import sys; assert sys.maxsize != 2**32-1" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.12"
    exit /b 0
  )
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize != 2**32-1" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=python"
    exit /b 0
  )
)
for %%P in ("%LocalAppData%\Programs\Python\Python312\python.exe" "%ProgramFiles%\Python312\python.exe" "C:\Python312\python.exe") do (
  if exist "%%~P" (
    "%%~P" -c "import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize != 2**32-1" >nul 2>&1
    if not errorlevel 1 (
      set "PYTHON_EXE=%%~P"
      exit /b 0
    )
  )
)
exit /b 0

:create_venv
echo [Setup] Creating Python 3.12 virtual environment...
"%PYTHON_EXE%" %PYTHON_ARGS% -m venv ".venv"
if errorlevel 1 (
  echo [ERROR] Virtual environment creation failed.
  pause
  exit /b 1
)

:verify_venv
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Existing .venv is not Python 3.12.
  echo Rename or delete the .venv directory, then run start.bat again.
  pause
  exit /b 1
)

if exist ".venv\installed.ok" goto cuda_check

echo [Setup] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto dependency_failure

echo [Setup] Installing application dependencies (first run can take a while)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto dependency_failure

echo Installation completed successfully>".venv\installed.ok"
goto cuda_check

:dependency_failure
echo.
echo [ERROR] Python dependencies could not be installed.
echo Check network connectivity and errors above, then run start.bat again.
pause
exit /b 1

:cuda_check
echo [Check] Checking NVIDIA / CUDA support...
".venv\Scripts\python.exe" -m app.cuda_check
if not errorlevel 1 goto launch
where nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo [ERROR] nvidia-smi was not found. Check NVIDIA graphics driver.
  echo Run nvidia-smi in a new CMD window and verify the GPU is listed.
  pause
  exit /b 1
)
echo.
echo [ACTION] NVIDIA GPU exists but Python cannot use CUDA.
echo This is usually a CPU-only PyTorch build. A CUDA-enabled wheel is needed.
choice /C JN /N /M "Install/repair CUDA PyTorch 12.8 automatically? [J/N] "
if errorlevel 2 (
  echo [INFO] Installation skipped. You can run cuda-repair.bat later.
  pause
  exit /b 1
)
call "%~dp0cuda-repair.bat" /quiet
if errorlevel 1 (
  echo [ERROR] CUDA repair failed. See the errors above.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.cuda_check
if errorlevel 1 (
  echo [ERROR] PyTorch still cannot use CUDA. Run cuda-diagnostics.bat and export dump.
  pause
  exit /b 1
)
goto launch

:launch
if not exist "config.env" copy "config.example.env" "config.env" >nul
set "PYTHONUTF8=1"
echo [Start] Qwen3-TTS Studio: http://127.0.0.1:7865
echo [Start] Keep this window open while using the app.
start "" "http://127.0.0.1:7865"
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 (
  echo [ERROR] Application exited with an error.
  pause
)
endlocal
