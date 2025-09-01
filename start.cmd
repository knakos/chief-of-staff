@echo off
echo ====================================
echo   CHIEF OF STAFF - Windows Startup
echo ====================================
echo.

:: Check if we're in the correct directory
if not exist "backend\app.py" (
    echo ERROR: Please run this script from the chief-of-staff root directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

:: Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js and try again
    pause
    exit /b 1
)

echo [1/5] Setting up backend virtual environment...
cd backend
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo [2/5] Activating virtual environment and installing dependencies...
call .venv\Scripts\activate
pip install -r requirements.txt

echo [3/5] Setting up environment file...
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit backend\.env and add your ANTHROPIC_API_KEY
    echo Press any key when you've added your API key...
    pause
)

echo [4/5] Initializing database...
python init_db.py

echo [5/5] Starting backend server...
echo Backend will start on http://127.0.0.1:8787
echo.
echo After backend starts, run start-frontend.cmd in another terminal
echo.
uvicorn app:app --host 127.0.0.1 --port 8787 --reload --reload-dir="." --reload-exclude=".venv/**" --reload-exclude="__pycache__/**" --reload-exclude="*.pyc" --log-level warning