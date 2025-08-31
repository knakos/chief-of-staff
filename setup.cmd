@echo off
echo ====================================
echo   CHIEF OF STAFF - Initial Setup
echo ====================================
echo.
echo This script will set up the Chief of Staff application on Windows.
echo.

:: Check if we're in the correct directory
if not exist "backend\app.py" (
    echo ERROR: Please run this script from the chief-of-staff root directory
    pause
    exit /b 1
)

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org and try again
    pause
    exit /b 1
)

:: Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from nodejs.org and try again
    pause
    exit /b 1
)

echo ✓ Python found: 
python --version
echo ✓ Node.js found: 
node --version
echo.

echo [1/6] Creating backend virtual environment...
cd backend
python -m venv .venv

echo [2/6] Installing backend dependencies...
call .venv\Scripts\activate
pip install -r requirements.txt

echo [3/6] Creating environment configuration...
if not exist ".env" (
    copy .env.example .env
    echo Created .env file from template
) else (
    echo .env file already exists
)

echo [4/6] Installing frontend dependencies...
cd ..
npm install

echo [5/6] Testing backend setup...
cd backend
call .venv\Scripts\activate
python test_setup.py
if %errorlevel% neq 0 (
    echo.
    echo Setup test failed. Please check the error messages above.
    pause
    exit /b 1
)
cd ..

echo [6/6] Setup complete!
echo.
echo ====================================
echo   NEXT STEPS:
echo ====================================
echo 1. Edit backend\.env and add your ANTHROPIC_API_KEY
echo    (Get it from: https://console.anthropic.com/)
echo.
echo 2. For Outlook integration, also add to backend\.env:
echo    MICROSOFT_CLIENT_ID=your_client_id
echo    MICROSOFT_CLIENT_SECRET=your_client_secret
echo.
echo 3. To start the application:
echo    Terminal 1: start.cmd          (Backend)
echo    Terminal 2: start-frontend.cmd (Frontend)
echo.
echo 4. For Outlook COM support:
echo    - Make sure Outlook is running with knakos@nbg.gr logged in
echo    - Run Command Prompt as Administrator
echo    - In the app, type: /outlook connect
echo.
echo Press any key to exit...
pause