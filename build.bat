@echo off
REM Build script for Faceit Discord Status executable
REM This script creates a standalone .exe file using PyInstaller

echo ========================================
echo  Faceit Discord Status - Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not available.
    echo Please ensure pip is installed with Python.
    pause
    exit /b 1
)

REM Install/upgrade PyInstaller
echo Installing/upgrading PyInstaller...
pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

REM Install project dependencies
echo.
echo Installing project dependencies...
pip install -r requirements.txt
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
pyinstaller FaceitDiscordStatus.spec --clean
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
