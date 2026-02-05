@echo off
echo ========================================
echo Camera Monitor Web Service - Quick Start
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Flask not found. Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Checking required files...
if not exist "Easy_IP_3.py" (
    echo ERROR: Easy_IP_3.py not found
    echo Please ensure all files are in the same directory
    pause
    exit /b 1
)

if not exist "camera_tracker.py" (
    echo ERROR: camera_tracker.py not found
    echo Please ensure all files are in the same directory
    pause
    exit /b 1
)

if not exist "templates\index.html" (
    echo ERROR: templates\index.html not found
    echo Please ensure the templates folder exists
    pause
    exit /b 1
)

echo.
echo All checks passed!
echo.
echo Starting web service...
echo Open your browser to: http://localhost:5000
echo Press Ctrl+C to stop the service
echo.
echo ========================================
echo.

python camera_web_service.py

pause
