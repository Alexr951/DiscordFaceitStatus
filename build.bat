@echo off
REM Build script for Faceit Discord Status executable
REM This script creates a standalone .exe file using PyInstaller

echo ========================================
echo  Faceit Discord Status - Build Script
echo ========================================
echo.

REM Check if Python is installed, including common Anaconda paths
set PYTHON_CMD=python

REM Try default python first
python --version >nul 2>&1
if not errorlevel 1 goto :python_found

REM Try common Anaconda locations
set ANACONDA_PATHS=^
%USERPROFILE%\anaconda3;^
%USERPROFILE%\Anaconda3;^
%USERPROFILE%\miniconda3;^
%USERPROFILE%\Miniconda3;^
D:\Users\%USERNAME%\anaconda3;^
D:\Users\%USERNAME%\Anaconda3;^
C:\ProgramData\Anaconda3;^
C:\ProgramData\miniconda3

for %%p in (%ANACONDA_PATHS%) do (
    if exist "%%p\python.exe" (
        echo Found Anaconda Python at: %%p
        set "PATH=%%p;%%p\Scripts;%%p\Library\bin;%PATH%"
        set "PYTHON_CMD=%%p\python.exe"
        goto :python_found
    )
)

echo ERROR: Python is not installed or not in PATH.
echo.
echo If you're using Anaconda, you can either:
echo   1. Run this from Anaconda Prompt
echo   2. Add Anaconda to your PATH manually
echo.
pause
exit /b 1

:python_found
echo Using Python: %PYTHON_CMD%
%PYTHON_CMD% --version

REM Check if pip is available
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not available.
    echo Please ensure pip is installed with Python.
    pause
    exit /b 1
)

REM Install/upgrade PyInstaller
echo.
echo Installing/upgrading PyInstaller...
%PYTHON_CMD% -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

REM Install project dependencies
echo.
echo Installing project dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM Clean previous build
echo.
echo Cleaning previous build artifacts...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build the executable
echo.
echo Building executable...
%PYTHON_CMD% -m PyInstaller FaceitDiscordStatus.spec --clean
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

REM Copy .env.example to dist folder
echo.
echo Copying configuration template...
copy ".env.example" "dist\.env.example" >nul

REM Create a README for the dist folder
echo.
echo Creating distribution README...
(
echo Faceit Discord Status - Standalone Executable
echo ==============================================
echo.
echo SETUP INSTRUCTIONS:
echo.
echo 1. Copy the .env.example file to .env
echo 2. Edit the .env file with your credentials:
echo    - FACEIT_API_KEY: Get from https://developers.faceit.com/
echo    - FACEIT_NICKNAME: Your FACEIT username ^(case-sensitive^)
echo    - DISCORD_APP_ID: Create at https://discord.com/developers/applications
echo.
echo 3. Run FaceitDiscordStatus.exe
echo.
echo The application will appear in your system tray.
echo Right-click the tray icon to access settings and controls.
echo.
echo NOTES:
echo - The .env file must be in the same folder as the executable
echo - A config.json file will be created automatically for your preferences
echo - Logs are stored in a 'logs' folder
) > "dist\README.txt"

echo.
echo ========================================
echo  BUILD COMPLETE!
echo ========================================
echo.
echo Output: dist\FaceitDiscordStatus.exe
echo.
echo Before running:
echo 1. Copy dist\.env.example to dist\.env
echo 2. Edit dist\.env with your API credentials
echo.
pause
