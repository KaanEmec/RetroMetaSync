@echo off
setlocal

REM Build RetroMetaSync as Windows executable (dist/RetroMetaSync/RetroMetaSync.exe)
REM Requires: pip install pyinstaller customtkinter

cd /d "%~dp0"

echo Checking dependencies...
python -c "import customtkinter" 2>nul || (
    echo Installing customtkinter...
    pip install customtkinter
)
python -c "import PyInstaller" 2>nul || (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building RetroMetaSync.exe...
python -m PyInstaller --noconfirm --clean RetroMetaSync.spec

if errorlevel 1 (
    echo.
    echo Build failed. Press any key to exit...
    pause >nul
    exit /b 1
)

echo.
echo ========================================
echo   Build complete!
echo ========================================
echo.
echo   IMPORTANT: Run the exe from dist, NOT from build!
echo.
echo   Correct:  dist\RetroMetaSync\RetroMetaSync.exe
echo   Wrong:    build\... (will fail with "Failed to load Python DLL")
echo.
echo   To run:  run_retrometasync.bat
echo   Or:      dist\RetroMetaSync\RetroMetaSync.exe
echo.
echo   To distribute: Copy the entire dist\RetroMetaSync folder.
echo.
start "" "dist\RetroMetaSync"
pause
