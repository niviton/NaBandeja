@echo off
setlocal
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0schedule_db_backup_task.ps1" -EveryMinutes 30
if errorlevel 1 (
  echo.
  echo Falha ao criar tarefa automatica.
  exit /b 1
)
echo.
echo Backup + git push automatico configurado com sucesso.
echo Frequencia: 30 minutos.
endlocal
