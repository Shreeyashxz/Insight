@echo off
TITLE Insight Sentinel - Auto Launcher
CLS

ECHO ========================================================
ECHO      INSIGHT - AI LEGAL SENTINEL (Auto-Setup)
ECHO ========================================================
ECHO This script will set up a stable environment for the app.
ECHO.
SET "PYTHON_EXECUTABLE="

:: 1. Search for a stable Python version
ECHO [1/5] Searching for a stable Python version (e.g., 3.12, 3.11)...

:: Check for Python 3.12 first
py -3.12 --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    ECHO    - Found Python 3.12.
    SET "PYTHON_EXECUTABLE=py -3.12"
    GOTO PYTHON_FOUND
)

:: If not found, check for Python 3.11
py -3.11 --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    ECHO    - Found Python 3.11.
    SET "PYTHON_EXECUTABLE=py -3.11"
    GOTO PYTHON_FOUND
)

:: If neither is found, show an error
IF NOT DEFINED PYTHON_EXECUTABLE (
    ECHO.
    ECHO ###################################################################
    ECHO ## CRITICAL ERROR: No stable Python version found (e.g., 3.12 or 3.11).
    ECHO ## This app requires a stable Python version to work correctly.
    ECHO ## Please install Python 3.11 or 3.12 from python.org
    ECHO ## Make sure to check "Add python.exe to PATH" during installation.
    ECHO ###################################################################
    ECHO.
    PAUSE
    EXIT /B
)

:PYTHON_FOUND
ECHO    - Using %PYTHON_EXECUTABLE% to build the environment.

:: 2. Check for database state
ECHO.
ECHO [2/5] Checking for existing knowledge base...
IF EXIST "%~dp0legal_db" (
    ECHO    - Found existing 'legal_db' database.
    ECHO    - Preserving your indexed legal documents by default.
    CHOICE /C YN /D N /T 4 /M "Reset and wipe database for a clean start? [Y/N] (Continuing in 4s)"
    IF ERRORLEVEL 2 (
        ECHO    - Retaining existing knowledge base.
    ) ELSE (
        ECHO    - Deleting old database...
        RMDIR /S /Q "%~dp0legal_db"
        ECHO    - Database wiped cleanly.
    )
) ELSE (
    ECHO    - No existing database found. Clean start.
)

:: 3. Create or verify the virtual environment
ECHO.
ECHO [3/5] Setting up isolated Python environment...
IF NOT EXIST "%~dp0.venv\Scripts\python.exe" (
    ECHO    - Virtual environment not found. Creating it now...
    %PYTHON_EXECUTABLE% -m venv "%~dp0.venv"
    IF %ERRORLEVEL% NEQ 0 (
        ECHO    - ERROR: Failed to create the virtual environment.
        PAUSE
        EXIT /B
    )
    ECHO    - Virtual environment created successfully.
) ELSE (
    ECHO    - Virtual environment already exists.
)

:: 4. Install/Update Libraries inside the virtual environment
ECHO.
ECHO [4/5] Installing/Updating Python Libraries...
"%~dp0.venv\Scripts\pip.exe" install -r "%~dp0requirements.txt"
IF %ERRORLEVEL% NEQ 0 (
    ECHO.
    ECHO ###################################################################
    ECHO ## ERROR: Failed to install required libraries.
    ECHO ## Please check your internet connection and try again.
    ECHO ###################################################################
    ECHO.
    PAUSE
    EXIT /B
)
ECHO    - All libraries are ready.

:: 5. Launch App
ECHO.
ECHO ========================================================
ECHO [5/5] LAUNCHING INSIGHT SENTINEL...
ECHO ========================================================
ECHO.

"%~dp0.venv\Scripts\streamlit.exe" run "%~dp0Insight.py"
