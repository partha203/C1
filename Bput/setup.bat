@echo off
setlocal enabledelayedexpansion
title CampusOne Setup
echo ============================================
echo   CampusOne Setup
echo   Campus Life, Debugged.
echo ============================================
echo.

REM ---- 1. Check Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on your system.
    echo Please install Python 3.10 or newer from https://www.python.org/downloads/
    echo and make sure "Add Python to PATH" is checked during installation.
    pause
    exit /b 1
)
echo [OK] Python found:
python --version
echo.

REM ---- 2. Create virtual environment ----
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists, skipping creation.
)
echo.

REM ---- 3. Install requirements ----
echo Installing dependencies...
call venv\Scripts\python.exe -m pip install --upgrade pip >nul
call venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.
echo.

REM ---- 4. Set up .env if missing ----
if not exist .env (
    copy .env.example .env >nul
    echo [OK] Created .env from template. Edit it later if you want email/AI features.
)
echo.

REM ---- 5. Initialize + seed database ----
echo Initializing database with demo data...
call venv\Scripts\python.exe init_db.py
if errorlevel 1 (
    echo [ERROR] Database initialization failed.
    pause
    exit /b 1
)
echo.
echo ============================================
echo   Setup complete!
echo   Run "run.bat" to start CampusOne.
echo ============================================
pause
