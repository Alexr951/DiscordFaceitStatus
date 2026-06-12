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

REM Create a README for the dist folder
echo.
echo Creating distribution README...
(
echo Faceit Discord Status
echo =====================
echo.
echo QUICK START:
echo.
echo 1. Run FaceitDiscordStatus.exe
echo 2. It finds your FACEIT account via your Steam login - click Save ^& Start
echo 3. Done! The app lives in your system tray ^(near the clock^).
echo.
echo Right-click the tray icon for settings:
echo - Settings... : change nickname and what shows in Discord
echo - Start with Windows : launch automatically on boot
echo - View Current Match : open your match page on Faceit
echo.
echo Your settings and logs are stored in %%APPDATA%%\FaceitDiscordStatus
) > "dist\README.txt"

echo.
echo ========================================
echo  BUILD COMPLETE!
echo ========================================
echo.
echo Output: dist\FaceitDiscordStatus.exe
echo.
echo Share dist\FaceitDiscordStatus.exe - it is fully self-contained.
echo.
pause
