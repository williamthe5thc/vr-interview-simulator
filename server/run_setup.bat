@echo off
REM Setup script for VR Interview System (Windows)
echo Setting up VR Interview System...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from python.org
    pause
    exit /b 1
)

REM Run the setup script
echo Running setup script...
python setup.py %*

if %errorlevel% neq 0 (
    echo.
    echo Setup failed with error code %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo Setup completed successfully!
echo.
echo To start the server, run: run_server.bat
echo.
pause
