param(
  [string]$TaskName = "NaBandeja-DB-Backup-GitPush",
  [int]$EveryMinutes = 30,
  [string]$ScriptPath = ""
)

$ErrorActionPreference = "Stop"

if ($EveryMinutes -lt 5) {
  throw "EveryMinutes deve ser no minimo 5"
}

if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
  $ScriptPath = Join-Path $PSScriptRoot "auto_backup_git_push.ps1"
}

$ScriptPath = [System.IO.Path]::GetFullPath($ScriptPath)
if (!(Test-Path $ScriptPath)) {
  throw "Script nao encontrado: $ScriptPath"
}

$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

schtasks /Delete /TN "$TaskName" /F 2>$null | Out-Null

schtasks /Create /TN "$TaskName" /SC MINUTE /MO $EveryMinutes /TR "$taskCommand" /F | Out-Null

Write-Host "Tarefa criada com sucesso: $TaskName"
Write-Host "Executa a cada $EveryMinutes minutos"
Write-Host "Script: $ScriptPath"
Write-Host "Para remover depois: schtasks /Delete /TN `"$TaskName`" /F"
