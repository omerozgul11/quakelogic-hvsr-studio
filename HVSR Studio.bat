@echo off
setlocal
title QuakeLogic HVSR Studio
cd /d "%~dp0"
set "PY=%~dp0runtime\win-x64\python\python.exe"
if not exist "%PY%" set "PY=%~dp0engine\.venv\Scripts\python.exe"
if not exist "%PY%" (
    where py >nul 2>nul && (set "PY=py -3.12") || (set "PY=python")
)
%PY% "%~dp0launcher\launch.py" %*
if errorlevel 1 (
    echo.
    echo HVSR Studio stopped with an error. Log files are in the data\logs folder.
    pause
)
endlocal
