@echo off
set PYTHONUTF8=1
call "%~dp0RUN_RUNTIME.bat" "%~dp0tools\start_ninfer.py"  %*
pause
