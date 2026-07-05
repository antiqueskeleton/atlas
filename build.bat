@echo off
setlocal

echo ============================================================
echo   Atlas AI  ^|  Build Script  ^|  v0.9.4
echo   dweeb.co
echo ============================================================
echo.

REM ── Prerequisites check ───────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH.
    exit /b 1
)

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller not found.
    echo        Install with:  pip install pyinstaller
    exit /b 1
)

REM ── Step 1: Generate atlas.ico ────────────────────────────────────────────
echo [1/3]  Generating atlas.ico...
echo.
python scripts\make_ico.py
if errorlevel 1 (
    echo WARNING: ICO generation failed. Continuing without custom icon.
    echo          Install Pillow if missing:  pip install Pillow
)
echo.

REM ── Step 2: PyInstaller ───────────────────────────────────────────────────
echo [2/3]  Building distributable with PyInstaller...
echo.

REM Pre-clean build and dist dirs; use PowerShell -LiteralPath to avoid prefix issues
if exist "build\atlas" (
    powershell -NoProfile -Command "Remove-Item -Recurse -Force -LiteralPath '.\build\atlas'" >nul 2>&1
)
if exist "dist\Atlas AI" (
    powershell -NoProfile -Command "Remove-Item -Recurse -Force -LiteralPath '.\dist\Atlas AI'" >nul 2>&1
)

python -m PyInstaller atlas.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed. Fix errors above and retry.
    exit /b 1
)
echo.
echo        PyInstaller OK  -^>  dist\Atlas AI\

REM ── Step 3: Inno Setup ────────────────────────────────────────────────────
echo.
echo [3/3]  Building installer with Inno Setup...
echo.

set ISCC_64="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set ISCC_ALT="C:\Program Files\Inno Setup 6\ISCC.exe"

if exist %ISCC_64% (
    %ISCC_64% installer\atlas_installer.iss
) else if exist %ISCC_ALT% (
    %ISCC_ALT% installer\atlas_installer.iss
) else (
    echo WARNING: Inno Setup 6 not found at standard paths.
    echo          Download from https://jrsoftware.org/isdl.php
    echo          Then run manually:
    echo          "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\atlas_installer.iss
    goto :done
)

if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETE
echo   Installer:  dist\installer\AtlasAI-v0.9.4-Setup.exe
echo ============================================================

:done
endlocal
