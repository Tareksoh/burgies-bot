@echo off
chcp 65001 >nul
title Discord Music Bot
color 0A

echo ============================================
echo    Discord Music Bot
echo ============================================
echo.

:: Check .env exists
if not exist "%~dp0.env" (
    color 0C
    echo  ERROR: .env file not found!
    echo.
    echo  1. Copy ".env.example" and rename the copy to ".env"
    echo  2. Open ".env" with Notepad
    echo  3. Paste your Discord bot token
    echo  4. Save and close
    echo  5. Run this file again
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
echo  Starting bot...
echo  (Don't close this window! The bot stops if you close it)
echo  Press Ctrl+C to stop the bot.
echo.
echo ============================================
echo.

python bot.py

echo.
echo ============================================
echo  Bot stopped.
echo ============================================
echo.
pause
