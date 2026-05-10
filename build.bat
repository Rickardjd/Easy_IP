@echo off
setlocal EnableDelayedExpansion
title Easy IP - Build

echo.
echo ============================================================
echo  Easy IP  ^|  Build Script
echo ============================================================
echo.

:: ── 0. Verify Python ──────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Install Python 3.9+ and retry.
    goto :fail
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Python : %%v

:: ── 1. Install / upgrade build tools ─────────────────────────────────────
echo.
echo [1/4] Installing build requirements...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install of runtime requirements failed.
    goto :fail
)
python -m pip install -q -r requirements_build.txt
if errorlevel 1 (
    echo [ERROR] pip install of build requirements failed.
    goto :fail
)
echo       Done.

:: ── 2. Generate icon ──────────────────────────────────────────────────────
echo.
echo [2/4] Generating icon...
python assets\create_icon.py
if errorlevel 1 (
    echo [ERROR] Icon generation failed. Check that Pillow is installed.
    goto :fail
)

:: ── 3. Bundle with PyInstaller ────────────────────────────────────────────
echo.
echo [3/4] Building executable with PyInstaller...

:: Resolve package paths using the launcher Python (which has user site-packages).
:: These are passed to the spec via environment variables so the spec doesn't
:: need to import packages itself (which fails in PyInstaller's stripped context).
for /f "usebackq delims=" %%i in (`python -c "import textual,os;print(os.path.dirname(textual.__file__))"`) do set EASYIP_TEXTUAL_DIR=%%i
for /f "usebackq delims=" %%i in (`python -c "import rich,os;print(os.path.dirname(rich.__file__))"`) do set EASYIP_RICH_DIR=%%i

if not defined EASYIP_TEXTUAL_DIR (
    echo [ERROR] Could not locate textual package. Run: python -m pip install textual
    goto :fail
)
if not defined EASYIP_RICH_DIR (
    echo [ERROR] Could not locate rich package. Run: python -m pip install rich
    goto :fail
)

echo       textual  -> %EASYIP_TEXTUAL_DIR%
echo       rich     -> %EASYIP_RICH_DIR%

python -m PyInstaller easy_ip.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    goto :fail
)
echo       Bundle written to:  dist\Easy_IP\

:: ── 4. Create Windows installer with Inno Setup ──────────────────────────
echo.
echo [4/4] Building Windows installer...

:: Search common Inno Setup install locations
set ISCC=
for %%p in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
) do (
    if exist %%p (
        set ISCC=%%p
        goto :found_iscc
    )
)

:: Not found — offer a portable alternative
echo.
echo [WARN] Inno Setup not found. Skipping installer creation.
echo        Download from: https://jrsoftware.org/isinfo.php
echo        Then re-run this script, or run manually:
echo          "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
goto :shortcut

:found_iscc
echo       Using: !ISCC!
!ISCC! installer\setup.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed. Check installer\setup.iss for errors.
    goto :fail
)
echo       Installer written to:  dist\Easy_IP_Setup_1.0.exe

:: ── 5. Create desktop shortcut ───────────────────────────────────────────
:shortcut
echo.
echo [5/5] Creating desktop shortcut...
set EXE_PATH=%CD%\dist\Easy_IP\Easy_IP.exe
powershell -NoProfile -Command ^
  "$s = (New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Easy IP.lnk');" ^
  "$s.TargetPath = '%EXE_PATH%';" ^
  "$s.IconLocation = '%CD%\assets\icon.ico,0';" ^
  "$s.Description = 'i-PRO Camera and Recorder IP Setup Tool';" ^
  "$s.Save()"
if errorlevel 1 (
    echo [WARN] Could not create desktop shortcut.
) else (
    echo       Shortcut created on Desktop.
)

:done
echo.
echo ============================================================
echo  Build complete!
echo ============================================================
echo.
echo  Standalone exe :  dist\Easy_IP\Easy_IP.exe
if defined ISCC (
    echo  Installer      :  dist\Easy_IP_Setup_1.0.exe
)
echo  Desktop icon   :  Easy IP.lnk
echo.
endlocal
exit /b 0

:fail
echo.
echo ============================================================
echo  Build FAILED. See errors above.
echo ============================================================
endlocal
exit /b 1
