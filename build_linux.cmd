@echo off
setlocal
title Void Compass - Linux testing build

where wsl.exe >nul 2>nul
if errorlevel 1 (
    echo Windows Subsystem for Linux is not installed.
    echo Install WSL with Ubuntu, restart Windows if requested, then run this file again.
    echo.
    echo     wsl --install -d Ubuntu
    echo.
    pause
    exit /b 1
)

for %%I in ("%~dp0.") do set "PROJECT_DIR=%%~fI"

echo Void Compass // Linux x86-64 testing build
echo Starting the default WSL distribution...
echo You may be asked for your Linux password if prerequisites are missing.
echo.

wsl.exe --cd "%PROJECT_DIR%" -- bash ./build_linux.sh
set "BUILD_RESULT=%ERRORLEVEL%"

echo.
if not "%BUILD_RESULT%"=="0" (
    echo Linux build failed with exit code %BUILD_RESULT%.
    echo Review the messages above for the missing prerequisite or build error.
) else (
    echo Linux release created successfully in:
    echo     %PROJECT_DIR%\release
)
echo.
pause
exit /b %BUILD_RESULT%
