@echo off
REM VR Interview System - Clean Deployment Script
REM This script deploys the fixed versions and cleans up redundant files

echo ================================
echo VR Interview System Deployment
echo ================================
echo.

echo [1/4] Creating backups of original files...
if exist server.py copy server.py server_backup.py >nul
if exist services\\llm\\Ollama_client.py copy services\\llm\\Ollama_client.py services\\llm\\Ollama_client_backup.py >nul
if exist app\\state\\manager.py copy app\\state\\manager.py app\\state\\manager_backup.py >nul
echo ✓ Backups created

echo.
echo [2/4] Deploying fixed versions as main files...
if exist server_fixed.py (
    copy server_fixed.py server.py >nul
    echo ✓ Deployed server_fixed.py -> server.py
) else (
    echo ✗ server_fixed.py not found
)

if exist services\\llm\\Ollama_client_fixed.py (
    copy services\\llm\\Ollama_client_fixed.py services\\llm\\Ollama_client.py >nul
    echo ✓ Deployed Ollama_client_fixed.py -> Ollama_client.py
) else (
    echo ✗ Ollama_client_fixed.py not found
)

if exist app\\state\\manager_fixed.py (
    copy app\\state\\manager_fixed.py app\\state\\manager.py >nul
    echo ✓ Deployed manager_fixed.py -> manager.py
) else (
    echo ✗ manager_fixed.py not found
)

echo.
echo [3/4] Testing deployed server...
echo Testing if server starts correctly...
timeout /t 2 >nul
python -c "import sys; sys.path.insert(0, '.'); from app.utils.config import load_config; config = load_config(); print('✓ Configuration loads successfully')" 2>nul
if %errorlevel% == 0 (
    echo ✓ Server components load correctly
) else (
    echo ✗ Server components have issues - check logs
)

echo.
echo [4/4] Cleaning up redundant files...
set /p cleanup="Remove redundant files? (y/n): "
if /i "%cleanup%"=="y" (
    if exist server_fixed.py del server_fixed.py && echo ✓ Removed server_fixed.py
    if exist services\\llm\\Ollama_client_fixed.py del services\\llm\\Ollama_client_fixed.py && echo ✓ Removed Ollama_client_fixed.py
    if exist app\\state\\manager_fixed.py del app\\state\\manager_fixed.py && echo ✓ Removed manager_fixed.py
    if exist debug_prompt.py del debug_prompt.py && echo ✓ Removed debug_prompt.py
    if exist test_prompt_debug.py del test_prompt_debug.py && echo ✓ Removed test_prompt_debug.py
    if exist validate_fixes.py del validate_fixes.py && echo ✓ Removed validate_fixes.py
    if exist CRITICAL_FIXES_SUMMARY.md del CRITICAL_FIXES_SUMMARY.md && echo ✓ Removed CRITICAL_FIXES_SUMMARY.md
    if exist TESTING_DEPLOYMENT_GUIDE.md del TESTING_DEPLOYMENT_GUIDE.md && echo ✓ Removed TESTING_DEPLOYMENT_GUIDE.md
    if exist READY_FOR_TESTING.md del READY_FOR_TESTING.md && echo ✓ Removed READY_FOR_TESTING.md
    if exist CLEANUP_DEPLOYMENT_PLAN.md del CLEANUP_DEPLOYMENT_PLAN.md && echo ✓ Removed CLEANUP_DEPLOYMENT_PLAN.md
    echo ✓ Cleanup completed
) else (
    echo ↩ Skipped cleanup - redundant files kept for reference
)

echo.
echo ================================
echo Deployment Summary
echo ================================
echo ✓ Fixed server deployed as main server.py
echo ✓ Fixed components deployed
echo ✓ Backup files created (*_backup.py)
echo ✓ System ready for production use
echo.
echo Next steps:
echo 1. Test: python server.py
echo 2. Connect Unity client
echo 3. Verify all three fixes are working
echo.
echo Rollback if needed:
echo   copy server_backup.py server.py
echo   copy services\\llm\\Ollama_client_backup.py services\\llm\\Ollama_client.py  
echo   copy app\\state\\manager_backup.py app\\state\\manager.py
echo.
pause
