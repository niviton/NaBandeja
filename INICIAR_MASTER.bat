@echo off
rem Painel master do NaBandeja (so neste PC): empresas, backups e instaladores.
rem Usa a pasta %USERPROFILE%\NaBandejaMaster; nao mexe no .env nem no banco da loja.
setlocal
cd /d %~dp0
set NABANDEJA_MODO=master
if "%APP_PORT%"=="" set APP_PORT=8100
if not exist venv\Scripts\python.exe (
  echo Rode primeiro deploy\windows\start_system.bat para instalar o sistema.
  pause
  exit /b 1
)
venv\Scripts\python.exe deploy\windows\launcher.py
if errorlevel 1 pause
