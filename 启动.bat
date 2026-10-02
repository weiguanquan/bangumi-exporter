@echo off
REM ---------------------------------------------------------------
REM  Bangumi collection exporter launcher.
REM  IMPORTANT: keep this file pure ASCII. cmd.exe parses .bat bytes
REM  with the OEM code page (936 on Chinese Windows), so UTF-8
REM  Chinese text here corrupts command parsing. All Chinese UI text
REM  is produced by the Python side instead.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set "BANGUMI_HOME=%~dp0"

REM Locate an interpreter: python -> py -> pythonw, each verified by running it
set "PY_CMD="
for %%P in (python.exe py.exe pythonw.exe) do (
    if not defined PY_CMD (
        %%~nP -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=%%~nP"
    )
)

if not defined PY_CMD goto :nopython

if /i "%PY_CMD%"=="pythonw" (
    start "" pythonw "%~dp0src\webui.py"
    exit /b 0
)

REM Single level of quoting, no pipeline: tee_run.py mirrors output to the log
start "Bangumi Exporter" cmd /k "chcp 65001 >nul & %PY_CMD% tools\tee_run.py"
exit /b 0

:nopython
echo ========================================
echo  ERROR: Python not found
echo.
echo  Please install Python 3.8+ and make sure
echo  "Add Python to PATH" is checked.
echo ========================================
pause
exit /b 1
