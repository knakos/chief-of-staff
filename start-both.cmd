@echo off
echo ====================================
echo   CHIEF OF STAFF - Complete Startup
echo ====================================
echo.
echo This will start both backend and frontend in separate windows.
echo Make sure you've run setup.cmd first and added your ANTHROPIC_API_KEY to backend\.env
echo.

:: Check if environment is set up
if not exist "backend\.env" (
    echo ERROR: Environment file not found. Please run setup.cmd first.
    pause
    exit /b 1
)

if not exist "backend\.venv" (
    echo ERROR: Virtual environment not found. Please run setup.cmd first.
    pause
    exit /b 1
)

echo Starting backend server in new window...
start "Chief of Staff - Backend" cmd /k "cd backend && .venv\Scripts\activate && uvicorn app:app --host 127.0.0.1 --port 8787 --reload"

echo Waiting 5 seconds for backend to start...
timeout /t 5 /nobreak >nul

echo Starting frontend application in new window...
start "Chief of Staff - Frontend" cmd /k "npm run dev"

echo.
echo Both services are starting in separate windows:
echo - Backend: http://127.0.0.1:8787
echo - Frontend: Electron application window
echo.
echo TIP: Once the app opens, try these commands:
echo   /outlook connect  - Connect to Outlook
echo   /outlook setup    - Create GTD folders  
echo   /help            - Show all commands
echo.
echo Press any key to exit this window...
pause