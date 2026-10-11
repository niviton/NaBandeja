@echo off
:: ============================================================
:: INSTALAR CERTIFICADO CA - Outros PCs da rede
:: Copie o arquivo rootCA.pem do PC servidor para este PC
:: Depois execute este arquivo como Administrador
:: ============================================================

NET SESSION >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRO: Execute este arquivo como Administrador!
    echo Clique com o botao direito > "Executar como administrador"
    pause
    exit /b 1
)

SET "CERT=%~dp0rootCA.pem"

IF NOT EXIST "%CERT%" (
    echo ERRO: Arquivo rootCA.pem nao encontrado!
    echo Copie o arquivo rootCA.pem do PC servidor para a mesma pasta que este .bat
    pause
    exit /b 1
)

echo.
echo Instalando certificado no Windows...
certutil -addstore "Root" "%CERT%"

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo Certificado instalado com sucesso!
    echo Chrome e Edge ja vao confiar no site automaticamente.
    echo Feche e reabra o navegador.
) ELSE (
    echo ERRO: Falha ao instalar o certificado.
)

echo.
pause
