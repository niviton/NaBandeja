@echo off
:: ============================================================
:: CONFIGURAR HTTPS - NaBandeja
:: Execute este arquivo UMA VEZ no PC servidor (como Administrador)
:: ============================================================

NET SESSION >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRO: Execute este arquivo como Administrador!
    echo Clique com o botao direito > "Executar como administrador"
    pause
    exit /b 1
)

SET "BASE=%~dp0..\.."
SET "CERTS=%BASE%\certs"

IF NOT EXIST "%CERTS%" mkdir "%CERTS%"

cd /d "%CERTS%"

echo.
echo ============================================================
echo   Configurando HTTPS para NaBandeja
echo ============================================================
echo.

:: Verifica ou baixa o mkcert
IF NOT EXIST "mkcert.exe" (
    echo [1/4] Baixando mkcert...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-windows-amd64.exe' -OutFile 'mkcert.exe'}"
    IF NOT EXIST "mkcert.exe" (
        echo ERRO: Falha ao baixar mkcert. Verifique sua conexao com a internet.
        pause
        exit /b 1
    )
) ELSE (
    echo [1/4] mkcert ja encontrado, pulando download.
)

:: Instala a CA local no Windows (browsers vao confiar automaticamente)
echo [2/4] Instalando certificado CA local no Windows...
mkcert.exe -install
IF %ERRORLEVEL% NEQ 0 (
    echo ERRO: Falha ao instalar CA local.
    pause
    exit /b 1
)

:: Descobre o IP local automaticamente
FOR /F "tokens=2 delims=:" %%i IN ('ipconfig ^| findstr /R "IPv4"') DO SET LAN_IP=%%i
SET LAN_IP=%LAN_IP: =%
echo     IP detectado: %LAN_IP%

:: Descobre o hostname
FOR /F %%i IN ('hostname') DO SET HOSTNAME=%%i

:: Gera o certificado SSL para todos os enderecos necessarios
echo [3/4] Gerando certificados SSL...
mkcert.exe -key-file key.pem -cert-file cert.pem %LAN_IP% %LAN_IP%.sslip.io localhost 127.0.0.1 %HOSTNAME% ::1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRO: Falha ao gerar certificados.
    pause
    exit /b 1
)

:: Copia o Root CA para distribuicao
FOR /F "delims=" %%i IN ('mkcert.exe -CAROOT') DO SET CAROOT=%%i
copy /Y "%CAROOT%\rootCA.pem" rootCA.pem >nul
echo     Root CA copiado para: %CERTS%\rootCA.pem

:: Libera a porta 443 para o usuario atual (evita precisar de admin toda vez)
echo [4/4] Liberando porta 443...
netsh http add urlacl url=https://+:443/ user="%USERNAME%" >nul 2>&1
netsh advfirewall firewall delete rule name="NaBandeja HTTPS" >nul 2>&1
netsh advfirewall firewall add rule name="NaBandeja HTTPS" dir=in action=allow protocol=TCP localport=443 >nul

echo.
echo ============================================================
echo   HTTPS CONFIGURADO COM SUCESSO!
echo ============================================================
echo.
echo   Acesse o sistema em: https://%LAN_IP%
echo.
echo   Para outros PCs na rede:
echo   - Abra a pasta: %CERTS%
echo   - Copie o arquivo "rootCA.pem" para o outro PC
echo   - Execute "instalar_certificado_pc.bat" nele
echo.
echo   Para celulares:
echo   - Inicie o sistema normalmente
echo   - No celular, abra: http://%LAN_IP%:8000/download-ca-cert
echo   - Baixe e instale o certificado
echo   - Android: Configuracoes > Seguranca > Instalar certificado
echo   - iPhone: Abrir arquivo > Instalar > Confiar no perfil
echo.
echo ============================================================
pause
