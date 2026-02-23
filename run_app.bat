@echo off
setlocal

REM Always run from project root (location of this .bat file)
cd /d "%~dp0"

REM Ensure package imports resolve without manual environment setup
set "PYTHONPATH=%cd%\src"

echo Launching RetroMetaSync...
python -m retrometasync.app

REM Keep console open only when startup/execution fails
if errorlevel 1 (
    echo.
    echo App exited with an error. Press any key to close...
    pause >nul
)

endlocal
