@echo off
setlocal EnableDelayedExpansion

:: ── Colors via ANSI (Windows 10+) ───────────────────────────────────────────
for /f %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"
set "GREEN=%ESC%[32m"
set "CYAN=%ESC%[36m"
set "YELLOW=%ESC%[33m"
set "RED=%ESC%[31m"
set "NC=%ESC%[0m"

cd /d "%~dp0"

echo.
echo %CYAN%╔══════════════════════════════════════╗%NC%
echo %CYAN%║     Invoice Processor — Web App      ║%NC%
echo %CYAN%╚══════════════════════════════════════╝%NC%
echo.

:: ── 1. Python ─────────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo %RED%✗ Python not found. Download it from https://python.org%NC%
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo %GREEN%✓ %%v found%NC%

:: ── 2. Poppler ────────────────────────────────────────────────────────────────
where pdftoppm >nul 2>&1
if not errorlevel 1 (
    echo %GREEN%✓ Poppler already installed%NC%
    goto :poppler_done
)

:: Try Chocolatey
where choco >nul 2>&1
if not errorlevel 1 (
    echo %CYAN%→ Installing Poppler via Chocolatey...%NC%
    choco install poppler -y
    goto :poppler_done
)

:: Try winget
where winget >nul 2>&1
if not errorlevel 1 (
    echo %CYAN%→ Installing Poppler via winget...%NC%
    winget install -e --id oschwartz10612.Poppler --accept-package-agreements --accept-source-agreements
    goto :poppler_done
)

:: Manual fallback
echo %YELLOW%⚠ Poppler not found and no package manager available.%NC%
echo %YELLOW%  Please install it manually:%NC%
echo %YELLOW%  1. Download from: https://github.com/oschwartz10612/poppler-windows/releases%NC%
echo %YELLOW%  2. Extract it and add the 'bin' folder to your PATH%NC%
echo %YELLOW%  3. Or set POPPLER_PATH=C:\path\to\poppler\bin and re-run this script%NC%
echo.
echo Press any key to continue anyway (app will fail on PDF processing without Poppler)...
pause >nul

:poppler_done

:: ── 3. Virtual environment ────────────────────────────────────────────────────
if not exist "venv\" (
    echo %CYAN%→ Creating virtual environment...%NC%
    python -m venv venv
)
echo %GREEN%✓ Virtual environment ready%NC%

:: Activate venv
call venv\Scripts\activate.bat

:: ── 4. Python dependencies ────────────────────────────────────────────────────
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo %CYAN%→ Installing Python dependencies...%NC%
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo %GREEN%✓ Dependencies installed%NC%
) else (
    echo %GREEN%✓ Dependencies already installed%NC%
)

:: ── 5. Check for API keys ─────────────────────────────────────────────────────
if "%OPENAI_API_KEY%"=="" if "%ANTHROPIC_API_KEY%"=="" (
    echo %YELLOW%⚠ No API keys found in environment.%NC%
    echo %YELLOW%  You can enter them in the browser, or set them to avoid typing each time:%NC%
    echo %YELLOW%  set OPENAI_API_KEY=sk-...%NC%
    echo %YELLOW%  set ANTHROPIC_API_KEY=sk-ant-...%NC%
    echo.
) else (
    if not "%OPENAI_API_KEY%"==""    echo %GREEN%✓ OPENAI_API_KEY set%NC%
    if not "%ANTHROPIC_API_KEY%"=="" echo %GREEN%✓ ANTHROPIC_API_KEY set%NC%
)

:: ── 6. Open browser after short delay ────────────────────────────────────────
set PORT=5000
if not "%PORT%"=="" set PORT=%PORT%

:: Launch browser in background after 1.5s delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:%PORT%"

:: ── 7. Start Flask ────────────────────────────────────────────────────────────
echo.
echo %GREEN%Starting Invoice Processor on http://localhost:%PORT%%NC%
echo %CYAN%Press Ctrl+C to stop.%NC%
echo.

python app.py

endlocal
