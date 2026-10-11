# Build executable for Sistema de Restaurante
# This script creates a standalone .exe with PyInstaller

$ErrorActionPreference = 'Stop'

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "NaBandeja - Build .exe" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project root
Set-Location "$PSScriptRoot\..\.."
$PROJECT_ROOT = Get-Location

Write-Host "[1/5] Verificando ambiente virtual..." -ForegroundColor Yellow
if (!(Test-Path "venv\Scripts\python.exe")) {
    Write-Error "Ambiente virtual nao encontrado. Execute: python -m venv venv"
    exit 1
}

Write-Host "[2/5] Instalando PyInstaller..." -ForegroundColor Yellow
& .\venv\Scripts\python.exe -m pip install --quiet pyinstaller

Write-Host "[3/5] Coletando arquivos estaticos do Django..." -ForegroundColor Yellow
& .\venv\Scripts\python.exe manage.py collectstatic --noinput --clear | Out-Null

Write-Host "[4/5] Construindo executavel com PyInstaller..." -ForegroundColor Yellow
Write-Host "    Isso pode levar alguns minutos..." -ForegroundColor Gray

# Clean previous build
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# Build using spec file
& .\venv\Scripts\python.exe -m PyInstaller --clean --noconfirm NaBandeja.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha ao construir executavel"
    exit 1
}

Write-Host "[5/5] Criando estrutura de pastas..." -ForegroundColor Yellow

# Create media folder structure in dist
$DIST_DIR = Join-Path $PROJECT_ROOT "dist\NaBandeja"
New-Item -ItemType Directory -Force -Path "$DIST_DIR\media\products" | Out-Null
New-Item -ItemType Directory -Force -Path "$DIST_DIR\media\settings" | Out-Null

# Copy README and documentation to dist
Copy-Item -Path "docs\deploy-windows.md" -Destination "$DIST_DIR\README.md" -Force
if (Test-Path "docs") {
    Copy-Item -Path "docs" -Destination "$DIST_DIR\docs" -Recurse -Force
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Green
Write-Host "Executavel criado com sucesso!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""
Write-Host "Localizacao: $DIST_DIR" -ForegroundColor White
Write-Host ""
Write-Host "Para executar:" -ForegroundColor Cyan
Write-Host "  cd dist\NaBandeja" -ForegroundColor White
Write-Host "  .\NaBandeja.exe" -ForegroundColor White
Write-Host ""
Write-Host "Requisitos no computador de destino:" -ForegroundColor Yellow
Write-Host "  - PostgreSQL instalado e rodando (ou usar SQLite)" -ForegroundColor Gray
Write-Host "  - Redis instalado e rodando" -ForegroundColor Gray
Write-Host "  - Arquivo .env configurado" -ForegroundColor Gray
Write-Host ""


