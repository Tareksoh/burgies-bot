@echo off
chcp 65001 >nul
title Discord Music Bot - Installer
color 0B

echo ============================================
echo    Discord Music Bot - Installer
echo ============================================
echo.

:: Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  ERROR: Python is not installed!
    echo.
    echo  Download it from: https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)
python --version
echo       OK!
echo.

:: Check FFmpeg
echo [2/4] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo.
    echo  WARNING: FFmpeg is not installed!
    echo  The bot needs FFmpeg to play audio.
    echo.
    echo  To install: Open PowerShell as Admin and run:
    echo       winget install ffmpeg
    echo  Then restart your terminal.
    echo.
    pause
)
echo       OK!
echo.

:: Uninstall discord.py if present, install requirements
echo [3/4] Installing dependencies (this may take a few minutes)...
echo.
pip uninstall discord.py -y >nul 2>&1
pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  ERROR: Failed to install dependencies!
    echo  Make sure you have internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo.
echo       OK!
echo.

:: Check .env
echo [4/4] Checking configuration...
if not exist "%~dp0.env" (
    color 0E
    echo.
    echo  You still need to set up your .env file!
    echo.
    echo  1. Copy ".env.example" and rename the copy to ".env"
    echo  2. Open ".env" with Notepad
    echo  3. Replace "your_discord_bot_token_here" with your bot token
    echo  4. Save and close
    echo.
    echo  Get your token from: https://discord.com/developers/applications
    echo.
) else (
    echo       .env file found!
    echo.
)

color 0A
echo ============================================
echo    Installation complete!
echo ============================================
echo.
echo  Next steps:
echo    1. Make sure .env has your bot token
echo    2. Double-click "start.bat" to run the bot
echo.
pause
