@echo off
setlocal

echo ============================================
echo  Building Academy System (one-file .exe)
echo ============================================
echo.

REM Clean previous build
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist

REM Build
python -m PyInstaller --clean --noconfirm academy_system.spec

if errorlevel 1 (
    echo.
    echo BUILD FAILED — see messages above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete.
echo  Output: dist\AcademySystem.exe
echo ============================================
echo.
echo User data will live at:
echo    %%LOCALAPPDATA%%\AcademySystem\
echo.
pause