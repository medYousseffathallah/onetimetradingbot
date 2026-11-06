@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================================
echo   BVMT Trading Intelligence - Local Decision-Support Terminal
echo   Mode: 100%% Localhost Only ^| Zero Autonomous Order Submission ^| Zero Cloud
echo ============================================================================
echo.

REM Force live LLM calls off unless explicitly set by the operator
if not defined BVMT_ALLOW_LIVE_LLM set "BVMT_ALLOW_LIVE_LLM=0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import streamlit" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Streamlit is not installed in .venv.
        echo Run the following command once to install the local dashboard dependency:
        echo     uv sync --locked --group dev --extra dashboard
        pause
        exit /b 1
    )
    echo Starting local Streamlit interface at http://127.0.0.1:8501 ...
    echo Press Ctrl+C in this window to shut down safely.
    ".venv\Scripts\python.exe" -m bvmt.cli dashboard %*
    exit /b %ERRORLEVEL%
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Neither .venv nor 'uv' was found.
    echo Please run first-time setup from PowerShell:
    echo     python -m pip install uv
    echo     python scripts/bootstrap.py
    echo     uv sync --locked --group dev --extra dashboard
    pause
    exit /b 1
)

echo Starting local Streamlit interface via uv at http://127.0.0.1:8501 ...
uv run --extra dashboard bvmt dashboard %*
exit /b %ERRORLEVEL%
