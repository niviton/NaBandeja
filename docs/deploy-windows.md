# Implantação no Windows

O NaBandeja roda num PC do estabelecimento, que funciona como servidor. Garçons, cozinha e gerente acessam pela rede local.

## Como o sistema roda

| Componente | Função |
|---|---|
| **Daphne** | Um único servidor para páginas e WebSocket (tempo real), na mesma porta |
| **WhiteNoise** | Entrega CSS, JS e ícones com `DEBUG` desligado |
| **SQLite** | Banco padrão, um arquivo só (`db.sqlite3`) |
| **PostgreSQL** | Opcional, para grandes volumes |

O [`deploy/windows/launcher.py`](../deploy/windows/launcher.py) faz tudo, nesta ordem:

1. cria o `.env` no primeiro início, com chave secreta e senha do gerente próprias;
2. aplica as migrações e garante um gerente ativo;
3. atualiza o atalho da Área de Trabalho;
4. sobe o servidor (e o HTTPS, se houver certificado em `certs/`);
5. abre o navegador e mostra o endereço para os celulares.

Na primeira vez, a **senha do gerente** aparece na janela do servidor e fica salva no `.env`.

## Atualizar um cliente

Dê duplo clique em **`ATUALIZAR.bat`**. Ele faz backup do banco em `backups/antes-de-atualizar/`, baixa a versão nova (`git pull`), atualiza as dependências e aplica as migrações.

## Iniciar pelo código-fonte

```powershell
.\INICIAR_PC_NOVO.bat           # primeira vez e uso diário
# ou
.\deploy\windows\start_system.bat
```

## Executável `.exe`

### Gerar

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\build_exe.ps1
```

O resultado fica em `dist\NaBandeja\NaBandeja.exe`.

### Usar

1. Copie a pasta `dist\NaBandeja\` para o PC do estabelecimento.
2. Copie `.env.example` para `.env` na mesma pasta e ajuste os valores.
3. Dê duplo clique em `NaBandeja.exe`. O navegador abre sozinho.

Se o executável não abrir, rode-o pelo terminal para ver a mensagem de erro:

```powershell
cd dist\NaBandeja
.\NaBandeja.exe
```

## Rede local e firewall

Para garçons e cozinha acessarem pelo celular:

1. Descubra o IP do PC com `ipconfig` (Endereço IPv4, ex.: `192.168.1.100`).
2. Adicione esse IP no `.env`:
   ```env
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
   ```
3. Libere as portas, no PowerShell **como Administrador**:
   ```powershell
   New-NetFirewallRule -DisplayName "NaBandeja" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```
4. Nos celulares, acesse `http://192.168.1.100:8000`.

A tela **Configurações** mostra os links de acesso prontos.

Portas usadas, que podem ser alteradas no `.env`:

| Variável | Padrão |
|---|---|
| `APP_PORT` | `8000` (páginas e tempo real) |
| `HTTPS_PORT` | `443` |

## HTTPS na rede local

O HTTPS é necessário para alguns recursos do PWA no celular.

1. Execute `deploy\windows\setup_ssl.bat` **como Administrador**. Ele gera os certificados e libera a porta 443.
2. Em cada celular ou PC, instale o certificado raiz. Ele pode ser baixado pelo próprio sistema (`/download-ca-cert`) ou instalado com `deploy\windows\instalar_certificado_pc.bat`.
3. Reinicie o sistema. Quando existe certificado, o launcher sobe em HTTPS sozinho.

## Atalho na Área de Trabalho

Ao iniciar, o sistema cria ou atualiza um atalho na Área de Trabalho com:

- **nome:** o nome da loja definido em Configurações;
- **ícone:** gerado a partir do logo da loja e salvo em `deploy/windows/icons/`.

Se você mudar o nome ou o logo, o atalho é atualizado na próxima vez que o sistema iniciar. Para forçar a atualização:

```powershell
python manage.py setup_desktop_shortcut
```

## PostgreSQL (opcional)

No `.env`:

```env
DB_ENGINE=postgres
POSTGRES_DB=nabandeja
POSTGRES_USER=nabandeja
POSTGRES_PASSWORD=<senha forte>
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_SSLMODE=prefer
```

Depois rode `python manage.py migrate`.
