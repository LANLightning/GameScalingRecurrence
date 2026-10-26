@echo off
setlocal
set "PYTHONUTF8=1"
if not exist "%~dp0runtime-env\Scripts\python.exe" goto missing
"%~dp0runtime-env\Scripts\python.exe" %*
exit /b %errorlevel%
:missing
echo Run SETUP_RUNTIME.bat first. Recreate the environment on each machine.
exit /b 1
