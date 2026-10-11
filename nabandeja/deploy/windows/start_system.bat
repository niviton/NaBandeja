@echo off
cd /d %~dp0\..\..

echo ========================================
echo    NaBandeja - Inicializacao Automatica
echo ========================================

if not exist venv\Scripts\python.exe (
  echo [1/4] Criando ambiente virtual...
  python -m venv venv
  if errorlevel 1 (
    echo Erro ao criar ambiente virtual. Verifique se o Python esta instalado.
    pause
    exit /b 1
  )
)

echo [2/4] Instalando/atualizando dependencias...
venv\Scripts\python.exe -m pip install --upgrade pip >nul
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Erro ao instalar dependencias.
  pause
  exit /b 1
)

echo [3/4] Aplicando migracoes do banco...
venv\Scripts\python.exe manage.py migrate
if errorlevel 1 (
  echo Erro ao aplicar migracoes.
  pause
  exit /b 1
)

echo [4/4] Iniciando sistema...
venv\Scripts\python.exe deploy\windows\launcher.py
