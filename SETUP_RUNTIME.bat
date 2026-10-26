@echo off
setlocal
set "PYTHONUTF8=1"
if not exist "%~dp0cache\setup-temp" mkdir "%~dp0cache\setup-temp"
set "TEMP=%~dp0cache\setup-temp"
set "TMP=%TEMP%"
python -c "import sys; assert sys.version_info >= (3,12), 'Install Python 3.12+ x64 (tested: 3.14.3)'"
if errorlevel 1 exit /b 1
python -m venv "%~dp0runtime-env"
if errorlevel 1 exit /b 1
"%~dp0runtime-env\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%~dp0requirements-runtime-lock.txt"
if errorlevel 1 exit /b 1
"%~dp0runtime-env\Scripts\python.exe" "%~dp0tools\verify_runtime.py"
exit /b %errorlevel%
