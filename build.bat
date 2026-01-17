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

REM Reinstall Pillow with pip to ensure bundled DLLs (fixes Anaconda issues)
echo.
echo Reinstalling Pillow to ensure proper DLL bundling...
%PYTHON_CMD% -m pip uninstall -y Pillow >nul 2>&1
%PYTHON_CMD% -m pip install --force-reinstall Pillow
if errorlevel 1 (
    echo WARNING: Pillow reinstall had issues, continuing anyway...
)

REM Clean previous build
echo.
echo Cleaning previous build artifacts...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Clear PyInstaller cache to ensure fresh DLL collection
echo Clearing PyInstaller cache...
if exist "%LOCALAPPDATA%\pyinstaller" rmdir /s /q "%LOCALAPPDATA%\pyinstaller"

REM Build the executable
echo.
echo Building executable...
%PYTHON_CMD% -m PyInstaller FaceitDiscordStatus.spec --clean
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

REM Create minimal .env file (API keys are embedded in the exe)
echo.
echo Creating configuration file...
(
echo # Faceit Discord Status Configuration
echo # Enter your FACEIT username below, or leave empty to be prompted on first run
echo FACEIT_NICKNAME=
) > "dist\.env"
echo Created .env file - user will be prompted for username on first run

REM Create a README for the dist folder
echo.
echo Creating distribution README...
(
echo Faceit Discord Status - Standalone Executable
echo ==============================================
echo.
echo QUICK START:
echo.
echo 1. Run FaceitDiscordStatus.exe
echo 2. Enter your FACEIT username when prompted ^(case-sensitive^)
echo 3. Done! The app will appear in your system tray.
echo.
echo Right-click the tray icon to access settings and controls.
echo.
echo TO CHANGE USERNAME LATER:
echo Right-click tray icon ^> "Change FACEIT Username..."
echo.
echo NOTES:
echo - A config.json file will be created for your preferences
echo - Logs are stored in a 'logs' folder
) > "dist\README.txt"

echo.
echo ========================================
echo  BUILD COMPLETE!
echo ========================================
echo.
echo Output: dist\FaceitDiscordStatus.exe
echo.
echo API keys are embedded in the executable.
echo Your friend will be prompted for their FACEIT username on first run.
echo.
echo To share: Send the 'dist' folder to your friend.
echo.
pause
