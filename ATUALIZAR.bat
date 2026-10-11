@echo off
setlocal
cd /d %~dp0

echo ========================================
echo    NaBandeja - Atualizar sistema
echo ========================================
echo.
echo Feche o sistema (janela do servidor) antes de continuar.
pause

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set HOJE=%%c-%%b-%%a
for /f "tokens=1-2 delims=:." %%a in ("%time: =0%") do set AGORA=%%a%%b

echo [1/4] Backup do banco antes de atualizar...
if not exist backups\antes-de-atualizar mkdir backups\antes-de-atualizar
if exist db.sqlite3 copy /y db.sqlite3 "backups\antes-de-atualizar\db_%HOJE%_%AGORA%.sqlite3" >nul
if errorlevel 1 (
  echo Falha ao copiar o banco. Atualizacao cancelada.
  pause
  exit /b 1
)

echo [2/4] Baixando a versao nova...
git pull --ff-only
if errorlevel 1 (
  echo Nao foi possivel atualizar pelo git. Nada foi alterado no banco.
  pause
  exit /b 1
)

echo [3/4] Atualizando dependencias...
set AUTOBAHN_USE_NVX=0
venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo Erro ao instalar dependencias.
  pause
  exit /b 1
)

echo [4/4] Atualizando o banco de dados...
venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 (
  echo Erro na migracao. O backup esta em backups\antes-de-atualizar\
  pause
  exit /b 1
)

echo.
echo Atualizado! Abra o sistema novamente.
pause
