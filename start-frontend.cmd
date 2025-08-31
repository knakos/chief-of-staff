@echo off
echo ====================================
echo   CHIEF OF STAFF - Frontend Startup
echo ====================================
echo.

:: Check if we're in the correct directory
if not exist "main.js" (
    echo ERROR: Please run this script from the chief-of-staff root directory
    echo Current directory: %CD%
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

:: Check if backend is running
echo Checking if backend is running on port 8787...
netstat -an | find "8787" >nul
if %errorlevel% neq 0 (
    echo WARNING: Backend doesn't appear to be running on port 8787
    echo Please make sure you've started the backend first using start.cmd
    echo.
    echo Press any key to continue anyway...
    pause
)

echo Installing frontend dependencies...
npm install

echo.
echo Starting Electron application...
echo This will open the Chief of Staff desktop application
echo.
echo TIP: Once open, try these commands:
echo   /outlook connect  - Connect to Outlook (COM first, then Graph API)
echo   /outlook setup    - Create GTD folders
echo   /help            - Show all available commands
echo.

npm run dev