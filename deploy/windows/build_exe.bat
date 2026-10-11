@echo off
REM Build NaBandeja Executable
REM Quick launcher for build_exe.ps1

echo ========================================
echo  NaBandeja - Gerar .exe
echo ========================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Pressione qualquer tecla para fechar...
    pause >nul
) else (
    echo.
    echo ERRO ao gerar executavel!
    echo Pressione qualquer tecla para fechar...
    pause >nul
    exit /b 1
)
