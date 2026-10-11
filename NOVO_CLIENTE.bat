@echo off
setlocal
cd /d %~dp0

echo ========================================
echo    NaBandeja - Novo Cliente
echo ========================================
echo.
set /p NOME=Nome da loja (ex: Pizzaria do Joao):
if "%NOME%"=="" (
  echo Nome obrigatorio.
  pause
  exit /b 1
)

if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe scripts\novo_cliente.py "%NOME%"
) else (
  python scripts\novo_cliente.py "%NOME%"
)
pause
