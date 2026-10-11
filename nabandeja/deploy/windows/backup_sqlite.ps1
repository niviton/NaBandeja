param(
  [string]$DbPath = "$PSScriptRoot\..\..\db.sqlite3",
  [string]$BackupDir = "C:\Backups\NaBandeja\sqlite",
  [int]$KeepCount = 60
)

$ErrorActionPreference = "Stop"

$DbPath = [System.IO.Path]::GetFullPath($DbPath)
if (!(Test-Path $DbPath)) {
  throw "Banco SQLite nao encontrado em: $DbPath"
}

if ($KeepCount -lt 1) {
  throw "KeepCount deve ser no minimo 1"
}

if (!(Test-Path $BackupDir)) {
  New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupDir "nabandeja_sqlite_$timestamp.sqlite3"
$hashFile = "$backupFile.sha256"

# Usa a API de backup do SQLite via Python para snapshot consistente.
$pythonScript = @"
import sqlite3
import sys

src_path = sys.argv[1]
dst_path = sys.argv[2]

src = sqlite3.connect(src_path)
dst = sqlite3.connect(dst_path)
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()

# Valida integridade basica do backup criado.
chk = sqlite3.connect(dst_path)
try:
    result = chk.execute('PRAGMA integrity_check;').fetchone()
    if not result or result[0] != 'ok':
        raise RuntimeError(f'integrity_check falhou: {result}')
finally:
    chk.close()
"@

python -c $pythonScript "$DbPath" "$backupFile"
if ($LASTEXITCODE -ne 0) {
  throw "Falha ao gerar backup SQLite"
}

$hash = Get-FileHash -Path $backupFile -Algorithm SHA256
"$($hash.Hash.ToLower())  $([System.IO.Path]::GetFileName($backupFile))" | Set-Content -Path $hashFile -Encoding UTF8

Get-ChildItem $BackupDir -Filter "nabandeja_sqlite_*.sqlite3" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -Skip $KeepCount |
  Remove-Item -Force

Get-ChildItem $BackupDir -Filter "nabandeja_sqlite_*.sqlite3.sha256" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -Skip $KeepCount |
  Remove-Item -Force

Write-Host "Backup SQLite concluido: $backupFile"
Write-Host "Checksum salvo: $hashFile"
