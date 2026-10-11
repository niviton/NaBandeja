@echo off
setlocal
cd /d %~dp0\..\..

echo ========================================
echo    NaBandeja - Inicializacao
echo ========================================

if not exist venv\Scripts\python.exe (
  echo [1/3] Criando ambiente virtual...
  python -m venv venv
  if errorlevel 1 (
    echo Erro ao criar ambiente virtual. Verifique se o Python 3.11+ esta instalado.
    pause
    exit /b 1
  )
)

echo [2/3] Conferindo dependencias...
rem Versao em Python puro do autobahn: nao exige compilador C no Windows.
set AUTOBAHN_USE_NVX=0
venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo Erro ao instalar dependencias. Verifique a conexao com a internet.
  pause
  exit /b 1
)

echo [3/3] Iniciando sistema...
venv\Scripts\python.exe deploy\windows\launcher.py
if errorlevel 1 pause
