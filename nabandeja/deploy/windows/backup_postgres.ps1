param(
  [string]$DbName = "nabandeja",
  [string]$DbUser = "nabandeja",
  [string]$DbHost = "127.0.0.1",
  [string]$DbPort = "5432",
  [string]$BackupDir = "C:\Backups\NaBandeja"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $BackupDir)) {
  New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = Join-Path $BackupDir "nabandeja_$timestamp.backup"

$env:PGPASSWORD = $env:POSTGRES_PASSWORD
pg_dump -h $DbHost -p $DbPort -U $DbUser -F c -b -v -f $file $DbName

if ($LASTEXITCODE -ne 0) {
  throw "Falha no backup"
}

Get-ChildItem $BackupDir -Filter "nabandeja_*.backup" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -Skip 30 |
  Remove-Item -Force

Write-Host "Backup concluído: $file"
