@echo off
REM ============================================================
REM  HumanWrite AI v1 - Windows launcher
REM  Double-click this file to start the app.
REM ============================================================
setlocal
title HumanWrite AI
cd /d "%~dp0"

echo.
echo  ========================================================
echo   HumanWrite AI v1
echo   Make Every Word Sound Naturally Yours.
echo  ========================================================
echo.

REM --- 1. Find Python -------------------------------------------------
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYCMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYCMD=python"
    ) else (
        echo  [ERROR] Python was not found on this computer.
        echo.
        echo  Please install Python 3.10 to 3.13 from https://www.python.org/downloads/
        echo  IMPORTANT: on the very first installer screen, tick
        echo  "Add python.exe to PATH" before clicking Install.
        echo  NOTE: Python 3.14+ is too new for some packages - use 3.12 or 3.13.
        echo.
        pause
        exit /b 1
    )
)
%PYCMD% --version

REM --- 2. Create the virtual environment if missing --------------------
if not exist "venv\Scripts\python.exe" (
    echo.
    echo  [1/3] First run: creating a private Python environment ^(one-time, ~1 min^)...
    %PYCMD% -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call "venv\Scripts\activate.bat"

REM --- 3. Install requirements if imports fail -------------------------
python -c "import flask, docx, reportlab, pypdf, requests" >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  [2/3] Installing required packages ^(one-time, needs internet^)...
    python -m pip install --upgrade pip >nul 2>nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  [ERROR] Package installation failed. Check your internet connection,
        echo  then double-click Start-Windows.cmd again.
        pause
        exit /b 1
    )
) else (
    echo  [2/3] Packages already installed - skipping.
)

REM --- 4. Start the app -------------------------------------------------
echo.
echo  [3/3] Starting HumanWrite AI...
echo.
echo  Opening http://127.0.0.1:4322 in your browser.
echo  Keep this window open while you use the app.
echo  To stop the app, close this window or press Ctrl+C.
echo.
timeout /t 2 >nul
start "" "http://127.0.0.1:4322"
python app.py

echo.
echo  The app has stopped.
pause
