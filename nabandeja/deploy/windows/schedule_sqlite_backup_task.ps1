param(
  [string]$TaskName = "NaBandeja-SQLite-Backup",
  [int]$EveryMinutes = 30,
  [string]$ScriptPath = "",
  [string]$DbPath = "",
  [string]$BackupDir = "",
  [int]$KeepCount = 60,
  [switch]$UseGoogleDrive
)

$ErrorActionPreference = "Stop"

function Resolve-GoogleDriveBackupDir {
  $candidates = @(
    (Join-Path $env:USERPROFILE "Google Drive\Meu Drive"),
    (Join-Path $env:USERPROFILE "Google Drive\My Drive"),
    "G:\Meu Drive",
    "G:\My Drive"
  )

  foreach ($basePath in $candidates) {
    if (Test-Path $basePath) {
      return (Join-Path $basePath "NaBandejaBackups\sqlite")
    }
  }

  return $null
}

if ($EveryMinutes -lt 5) {
  throw "EveryMinutes deve ser no minimo 5"
}

if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
  $ScriptPath = Join-Path $PSScriptRoot "backup_sqlite.ps1"
}

$ScriptPath = [System.IO.Path]::GetFullPath($ScriptPath)
if (!(Test-Path $ScriptPath)) {
  throw "Script nao encontrado: $ScriptPath"
}

if ($UseGoogleDrive -and [string]::IsNullOrWhiteSpace($BackupDir)) {
  $BackupDir = Resolve-GoogleDriveBackupDir
  if ([string]::IsNullOrWhiteSpace($BackupDir)) {
    throw "Google Drive nao encontrado. Informe -BackupDir manualmente ou instale/configure o Google Drive Desktop."
  }
}

if (![string]::IsNullOrWhiteSpace($BackupDir) -and !(Test-Path $BackupDir)) {
  New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$taskParts = @(
  "powershell.exe",
  "-NoProfile",
  "-ExecutionPolicy Bypass",
  "-File `"$ScriptPath`""
)

if (![string]::IsNullOrWhiteSpace($DbPath)) {
  $DbPath = [System.IO.Path]::GetFullPath($DbPath)
  $taskParts += "-DbPath `"$DbPath`""
}

if (![string]::IsNullOrWhiteSpace($BackupDir)) {
  $taskParts += "-BackupDir `"$BackupDir`""
}

if ($KeepCount -lt 1) {
  throw "KeepCount deve ser no minimo 1"
}
$taskParts += "-KeepCount $KeepCount"

$taskCommand = ($taskParts -join " ")

schtasks /Delete /TN "$TaskName" /F 2>$null | Out-Null
schtasks /Create /TN "$TaskName" /SC MINUTE /MO $EveryMinutes /TR "$taskCommand" /F | Out-Null

Write-Host "Tarefa criada com sucesso: $TaskName"
Write-Host "Executa a cada $EveryMinutes minutos"
Write-Host "Script: $ScriptPath"
if (![string]::IsNullOrWhiteSpace($DbPath)) {
  Write-Host "DbPath: $DbPath"
}
if (![string]::IsNullOrWhiteSpace($BackupDir)) {
  Write-Host "BackupDir: $BackupDir"
}
if ($UseGoogleDrive) {
  Write-Host "Modo Google Drive: habilitado"
}
Write-Host "KeepCount: $KeepCount"
Write-Host "Comando: $taskCommand"
Write-Host "Para remover depois: schtasks /Delete /TN `"$TaskName`" /F"
