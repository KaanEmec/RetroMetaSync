@echo off
REM Run the built RetroMetaSync executable.
REM IMPORTANT: Run this from the project root after building with build_exe.bat
REM The exe MUST be run from dist\RetroMetaSync\ - NOT from the build folder!

cd /d "%~dp0"

if not exist "dist\RetroMetaSync\RetroMetaSync.exe" (
    echo RetroMetaSync.exe not found. Build first with: build_exe.bat
    echo.
    pause
    exit /b 1
)

echo Starting RetroMetaSync...
start "" "dist\RetroMetaSync\RetroMetaSync.exe"
