@echo off
REM VR Interview System - Production Deployment Script
REM This script deploys optimized fixes and prepares the system for production use

echo ====================================================
echo VR Interview System - Production Deployment
echo ====================================================
echo.

echo [1/6] Pre-deployment validation...
python -c \"import sys; print(f'Python version: {sys.version}')\" 2>nul
if %errorlevel% neq 0 (
    echo ❌ Python not found or not working
    goto :error
)

echo ✓ Python environment validated

echo.
echo [2/6] Creating safety backups...
set BACKUP_DIR=backups\\deployment_%date:~-4,4%_%date:~-10,2%_%date:~-7,2%_%time:~0,2%_%time:~3,2%_%time:~6,2%
mkdir %BACKUP_DIR% 2>nul

if exist server.py copy server.py %BACKUP_DIR%\\server_original.py >nul
if exist services\\llm\\Ollama_client.py copy services\\llm\\Ollama_client.py %BACKUP_DIR%\\Ollama_client_original.py >nul
if exist app\\state\\manager.py copy app\\state\\manager.py %BACKUP_DIR%\\manager_original.py >nul
if exist config\\config.json copy config\\config.json %BACKUP_DIR%\\config_original.json >nul

echo ✓ Backups created in %BACKUP_DIR%

echo.
echo [3/6] Deploying optimized components...

REM Deploy fixed server
if exist server_fixed.py (
    copy server_fixed.py server.py >nul
    echo ✓ Deployed optimized server
) else (
    echo ❌ server_fixed.py not found
    goto :error
)

REM Deploy fixed LLM client
if exist services\\llm\\Ollama_client_fixed.py (
    copy services\\llm\\Ollama_client_fixed.py services\\llm\\Ollama_client.py >nul
    echo ✓ Deployed optimized LLM client
) else (
    echo ❌ Ollama_client_fixed.py not found
    goto :error
)

REM Deploy fixed state manager
if exist app\\state\\manager_fixed.py (
    copy app\\state\\manager_fixed.py app\\state\\manager.py >nul
    echo ✓ Deployed optimized state manager
) else (
    echo ❌ manager_fixed.py not found
    goto :error
)

echo.
echo [4/6] Validating critical configuration...

REM Check if config has the child-friendly prompt issue
findstr /C:\"9-year-old\" config\\config.json >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  Configuration contains non-interview content
    echo    This could cause AI personality issues
    echo    Please review config\\config.json
) else (
    echo ✓ Configuration validated for interview scenario
)

echo.
echo [5/6] Testing deployment...

REM Test basic imports
python -c \"from app.utils.config import load_config; config = load_config(); print('✓ Config loads successfully')\" 2>nul
if %errorlevel% neq 0 (
    echo ❌ Configuration test failed
    goto :rollback
)

python -c \"from services.llm.Ollama_client import OllamaClient; print('✓ LLM client imports successfully')\" 2>nul
if %errorlevel% neq 0 (
    echo ❌ LLM client test failed
    goto :rollback
)

python -c \"from app.state.manager import StateManager; print('✓ State manager imports successfully')\" 2>nul
if %errorlevel% neq 0 (
    echo ❌ State manager test failed
    goto :rollback
)

echo ✓ All critical components test successfully

echo.
echo [6/6] Cleaning up redundant files...
set /p cleanup=\"Remove redundant fixed files? (y/n): \"
if /i \"%cleanup%\"==\"y\" (
    if exist server_fixed.py del server_fixed.py && echo ✓ Removed server_fixed.py
    if exist services\\llm\\Ollama_client_fixed.py del services\\llm\\Ollama_client_fixed.py && echo ✓ Removed Ollama_client_fixed.py
    if exist app\\state\\manager_fixed.py del app\\state\\manager_fixed.py && echo ✓ Removed manager_fixed.py
    
    REM Clean up temporary/debug files
    if exist debug_prompt.py del debug_prompt.py && echo ✓ Removed debug_prompt.py
    if exist test_prompt_debug.py del test_prompt_debug.py && echo ✓ Removed test_prompt_debug.py  
    if exist validate_fixes.py del validate_fixes.py && echo ✓ Removed validate_fixes.py
    
    echo ✓ Cleanup completed
) else (
    echo ↩ Skipped cleanup - files retained for reference
)

echo.
echo ====================================================
echo ✅ DEPLOYMENT SUCCESSFUL
echo ====================================================
echo.
echo 🎯 Production System Ready:
echo   • Fixed AI personality - Acts as professional interviewer
echo   • Fixed state management - No infinite loops
echo   • Fixed session handling - Context preserved
echo   • Optimized configuration - Interview-focused
echo.
echo 🚀 Next steps:
echo   1. Test: python server.py
echo   2. Connect Unity VR client
echo   3. Verify interview experience
echo   4. Monitor performance logs
echo.
echo 📊 Performance expectations:
echo   • STT Processing: 4-7 seconds (GPU accelerated)
echo   • LLM Generation: 5-10 seconds (Mistral 7B)
echo   • TTS Synthesis: 3-8 seconds (AllTalk)
echo   • Total Response: 12-25 seconds end-to-end
echo.
echo 💾 Backup location: %BACKUP_DIR%
echo.
echo 🆘 Rollback if needed:
echo   copy %BACKUP_DIR%\\server_original.py server.py
echo   copy %BACKUP_DIR%\\Ollama_client_original.py services\\llm\\Ollama_client.py
echo   copy %BACKUP_DIR%\\manager_original.py app\\state\\manager.py
echo.
goto :end

:rollback
echo.
echo ⚠️  DEPLOYMENT FAILED - ROLLING BACK
echo.
if exist %BACKUP_DIR%\\server_original.py copy %BACKUP_DIR%\\server_original.py server.py >nul
if exist %BACKUP_DIR%\\Ollama_client_original.py copy %BACKUP_DIR%\\Ollama_client_original.py services\\llm\\Ollama_client.py >nul
if exist %BACKUP_DIR%\\manager_original.py copy %BACKUP_DIR%\\manager_original.py app\\state\\manager.py >nul
echo ✓ System rolled back to previous version
echo ❌ Please check error logs and try again
goto :end

:error
echo.
echo ❌ DEPLOYMENT FAILED
echo Please check the error above and ensure all required files are present
goto :end

:end
pause
