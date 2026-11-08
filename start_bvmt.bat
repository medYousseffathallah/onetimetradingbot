@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================================
echo   BVMT Trading Intelligence - Local Decision-Support Platform
echo   Mode: 100%% Localhost Only ^| Zero Autonomous Order Submission ^| Zero Cloud
echo ============================================================================
echo.

REM Force live LLM calls off unless explicitly set by the operator
if not defined BVMT_ALLOW_LIVE_LLM set "BVMT_ALLOW_LIVE_LLM=0"

REM Allow fallback to Streamlit via: start_bvmt.bat --streamlit
if /I "%~1"=="--streamlit" goto :START_STREAMLIT

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python virtual environment was not found at:
    echo         "%PYTHON_EXE%"
    echo Please run first-time setup from PowerShell:
    echo     uv sync --locked --group dev --extra dashboard
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [WARN] FastAPI or Uvicorn not installed in virtual environment. Falling back to Streamlit...
    goto :START_STREAMLIT
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js / npm.cmd not found on PATH. Falling back to Streamlit...
    goto :START_STREAMLIT
)

if not exist "%~dp0frontend\package.json" (
    echo [WARN] frontend\package.json not found. Falling back to Streamlit...
    goto :START_STREAMLIT
)

REM Check if backend port 8000 is already in use
netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port 8000 is already in use. A backend instance may already be running.
)

REM Check if frontend port 3000 is already in use
netstat -ano -p tcp | findstr /R /C:":3000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port 3000 is already in use. A frontend instance may already be running.
)

echo [1/2] Starting Local FastAPI Backend at http://127.0.0.1:8000 ...
start "BVMT FastAPI Backend" cmd /c ""%PYTHON_EXE%" -m uvicorn bvmt.api:app --host 127.0.0.1 --port 8000"

echo [2/2] Starting Next.js Modern Dashboard at http://127.0.0.1:3000 ...
echo       Press Ctrl+C in this window to stop the Next.js frontend.
echo.
cd /d "%~dp0frontend"
call npm.cmd run dev
exit /b %ERRORLEVEL%

:START_STREAMLIT
shift
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Streamlit is not installed in virtual environment.
        echo Run the following command once to install the local dashboard dependency:
        echo     uv sync --locked --group dev --extra dashboard
        pause
        exit /b 1
    )
    REM Check if port 8501 is already in use
    netstat -ano -p tcp | findstr /R /C:":8501 .*LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo [WARN] Port 8501 is already in use. A Streamlit instance may already be running.
    )
    echo Starting local Streamlit fallback interface at http://127.0.0.1:8501 ...
    echo Press Ctrl+C in this window to shut down safely.
    "%PYTHON_EXE%" -m bvmt.cli dashboard %1 %2 %3 %4 %5
    exit /b %ERRORLEVEL%
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Neither virtual environment nor 'uv' was found.
    pause
    exit /b 1
)

echo Starting local Streamlit fallback interface via uv at http://127.0.0.1:8501 ...
uv run --extra dashboard bvmt dashboard %1 %2 %3 %4 %5
exit /b %ERRORLEVEL%
