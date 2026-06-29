@echo off
setlocal

echo ============================================================
echo   Atlas AI  ^|  Build Script
echo   Firman Power Equipment
echo ============================================================
echo.

REM ── Prerequisites check ───────────────────────────────────────────────────
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo ERROR: pyinstaller not found.
    echo        Install with:  pip install pyinstaller
    exit /b 1
)

REM ── Step 1: PyInstaller ───────────────────────────────────────────────────
echo [1/2]  Building distributable with PyInstaller...
echo.
pyinstaller atlas.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed. Fix errors above and retry.
    exit /b 1
)
echo.
echo        PyInstaller OK  ->  dist\Atlas AI\

REM ── Step 2: Inno Setup ────────────────────────────────────────────────────
echo.
echo [2/2]  Building installer with Inno Setup...
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
echo   Installer:  dist\installer\AtlasAI-v0.2-Setup.exe
echo ============================================================

:done
endlocal
