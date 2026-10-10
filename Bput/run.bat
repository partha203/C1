@echo off
title CampusOne Server
echo ============================================
echo   Starting CampusOne...
echo ============================================

if not exist venv (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

if not exist database\campusone.db (
    echo [WARNING] Database not found. Running initial setup...
    call venv\Scripts\python.exe init_db.py
)

echo.
echo CampusOne will be available at:
echo   http://127.0.0.1:5000
echo.
echo Press CTRL+C in this window to stop the server.
echo ============================================
echo.

set FLASK_APP=app.py
call venv\Scripts\python.exe app.py

pause
