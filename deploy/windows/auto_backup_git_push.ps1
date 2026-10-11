param(
  [string]$RepoRoot = "$PSScriptRoot\..\..",
  [string]$DbPath = "",
  [string]$BackupDir = "",
  [int]$KeepCount = 40,
  [switch]$IncludeLiveDb,
  [string]$RemoteName = "origin",
  [string]$Branch = "",
  [string]$CommitPrefix = "chore: backup automatico do banco"
)

$ErrorActionPreference = "Stop"

function Write-Log {
  param([string]$Message)
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  "$stamp | $Message" | Tee-Object -FilePath $script:LogFile -Append
}

function Get-RelativePath {
  param(
    [Parameter(Mandatory = $true)][string]$BasePath,
    [Parameter(Mandatory = $true)][string]$TargetPath
  )

  $base = [System.IO.Path]::GetFullPath($BasePath)
  $target = [System.IO.Path]::GetFullPath($TargetPath)

  $baseUri = New-Object System.Uri(($base.TrimEnd('\\') + '\\'))
  $targetUri = New-Object System.Uri($target)
  $relativeUri = $baseUri.MakeRelativeUri($targetUri)
  return [System.Uri]::UnescapeDataString($relativeUri.ToString().Replace('/', '\\'))
}

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
if ([string]::IsNullOrWhiteSpace($DbPath)) {
  $DbPath = Join-Path $RepoRoot "db.sqlite3"
}
if ([string]::IsNullOrWhiteSpace($BackupDir)) {
  $BackupDir = Join-Path $RepoRoot "backups\db"
}

$logsDir = Join-Path $RepoRoot "backups\logs"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$LogFile = Join-Path $logsDir "db_backup_git_push.log"

Write-Log "=== INICIO DA ROTINA ==="
Write-Log "RepoRoot: $RepoRoot"
Write-Log "DbPath: $DbPath"
Write-Log "BackupDir: $BackupDir"

if (!(Test-Path $DbPath)) {
  throw "Banco nao encontrado em: $DbPath"
}

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
  throw "Git nao encontrado no PATH"
}

$insideWorkTree = git -C $RepoRoot rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $insideWorkTree.Trim() -ne "true") {
  throw "A pasta nao e um repositorio git valido: $RepoRoot"
}

if ([string]::IsNullOrWhiteSpace($Branch)) {
  $Branch = (git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
}
if ([string]::IsNullOrWhiteSpace($Branch) -or $Branch -eq "HEAD") {
  throw "Nao foi possivel identificar a branch atual"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$snapshot = Join-Path $BackupDir "db_$timestamp.sqlite3"
$latest = Join-Path $BackupDir "db_latest.sqlite3"

Copy-Item -Path $DbPath -Destination $snapshot -Force
Copy-Item -Path $DbPath -Destination $latest -Force
Write-Log "Backup criado: $snapshot"

$oldBackups = Get-ChildItem -Path $BackupDir -Filter "db_*.sqlite3" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -Skip $KeepCount
foreach ($old in $oldBackups) {
  Remove-Item -Path $old.FullName -Force
}
if ($oldBackups) {
  Write-Log "Backups antigos removidos: $($oldBackups.Count)"
}

$relativeSnapshot = Get-RelativePath -BasePath $RepoRoot -TargetPath $snapshot
$relativeLatest = Get-RelativePath -BasePath $RepoRoot -TargetPath $latest

if ($IncludeLiveDb) {
  $relativeDb = Get-RelativePath -BasePath $RepoRoot -TargetPath $DbPath
  git -C $RepoRoot add -f -- "$relativeDb"
  Write-Log "Arquivo do banco adicionado ao commit: $relativeDb"
} else {
  Write-Log "Banco vivo NAO sera commitado (IncludeLiveDb desativado)."
}

git -C $RepoRoot add -- "$relativeSnapshot" "$relativeLatest"
Write-Log "Snapshots adicionados ao commit"

$staged = git -C $RepoRoot diff --cached --name-only
if (-not $staged) {
  Write-Log "Nenhuma alteracao para commitar"
  Write-Log "=== FIM DA ROTINA ==="
  exit 0
}

$commitMessage = "$CommitPrefix ($timestamp)"
git -C $RepoRoot commit -m "$commitMessage"
Write-Log "Commit criado: $commitMessage"

git -C $RepoRoot push $RemoteName $Branch
if ($LASTEXITCODE -ne 0) {
  throw "Falha no git push"
}

Write-Log "Push realizado para $RemoteName/$Branch"
Write-Log "=== FIM DA ROTINA ==="
