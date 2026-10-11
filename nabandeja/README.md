# NaBandeja - Sistema de Gestão para Restaurantes (Django)

Sistema completo de gestão para restaurantes/lanchonetes desenvolvido em Django com **atualizações em tempo real via WebSocket**.

## ✨ Destaques

- 🔄 **Atualizações em Tempo Real**: WebSocket para sincronização instantânea sem recarregar páginas
- 📱 **PWA (Progressive Web App)**: Instalável em dispositivos móveis
- 🖥️ **Deploy Windows**: Executável para servidor LAN profissional
- 🔐 **Segurança**: Hardening completo com autenticação e autorização por recurso
- ⚡ **Performance**: Queries otimizadas e cache eficiente

## 📋 Funcionalidades

- **Login com Roles**: Garçom, Cozinha, Gerente
- **Gestão de Pedidos**: Mesa e Delivery com atualização em tempo real
- **Cozinha**: Visualização e controle de pedidos **em tempo real via WebSocket**
- **Dashboard do Gerente**: Estatísticas atualizadas automaticamente
- **Cardápio**: Categorias e produtos com controle de estoque
- **Relatórios**: Vendas por período, por garçom, produtos mais vendidos
- **Configurações**: Personalização da loja (nome, logo, cores)
- **Impressão**: Cupom não-fiscal com QR Code PIX
- **Notificações**: Toast messages para feedback instantâneo

## 🔄 Recursos em Tempo Real

O sistema utiliza **Django Channels + Redis + WebSocket** para proporcionar:

- ✅ Dashboard do gerente atualiza automaticamente (vendas, pedidos ativos, mesas ocupadas)
- ✅ Cozinha recebe novos pedidos instantaneamente sem recarregar
- ✅ Garçons veem atualizações de status dos pedidos em tempo real
- ✅ Sincronização entre múltiplos usuários simultâneos
- ✅ Notificações toast para eventos importantes
- ✅ Indicador de status da conexão em tempo real
- ✅ Reconexão automática em caso de falha

**Documentação completa:** [docs/REALTIME_FEATURES.md](docs/REALTIME_FEATURES.md)

## 🚀 Como Executar

### 1. Criar ambiente virtual (recomendado)

```bash
cd nabandeja
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Criar banco de dados

```bash
python manage.py makemigrations restaurante
python manage.py migrate
```

### 4. Criar dados iniciais

```bash
python manage.py shell
```

No shell, cole o conteúdo do arquivo `initial_data.py` ou execute:

```python
exec(open('initial_data.py').read())
```

Ou crie um superusuário manualmente:

```bash
python manage.py createsuperuser
```

### 5. Executar o servidor

```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000

## 🔐 Variáveis de Ambiente (recomendado)

Antes de subir em produção, configure:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG` (`false` em produção)
- `DJANGO_ALLOWED_HOSTS` (ex: `meudominio.com,www.meudominio.com`)
- `DJANGO_CSRF_TRUSTED_ORIGINS` (ex: `https://meudominio.com,https://www.meudominio.com`)
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- `NABANDEJA_INIT_ADMIN_PASSWORD` (senha inicial do usuário gerente no `initial_data.py`)

Para banco PostgreSQL mais seguro em produção:

- `DB_ENGINE=postgres`
- `POSTGRES_SSLMODE=require` (ou `verify-full` com certificados)
- `POSTGRES_SSLROOTCERT`, `POSTGRES_SSLCERT`, `POSTGRES_SSLKEY` (quando usar TLS mTLS)

## 👤 Usuários Padrão

Após executar `initial_data.py`:

| Usuário | Senha | Role |
|---------|-------|------|
| gerente | admin | Gerente (acesso total) |

## 📱 Views por Role

- **Garçom** (`/garcom/`): Fazer pedidos, ver carrinho
- **Cozinha** (`/cozinha/`): Ver e marcar pedidos como prontos
- **Gerente** (`/admin-panel/`): Dashboard, relatórios, cardápio, equipe, configurações

## 🗂️ Estrutura do Projeto

```
nabandeja/
├── nabandeja_project/          # Configurações Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── restaurante/             # App principal
│   ├── models.py            # User, Category, Product, Order, OrderItem, AppSettings
│   ├── views.py             # Todas as views
│   ├── forms.py             # Formulários
│   ├── urls.py              # Rotas
│   └── admin.py             # Admin Django
├── templates/               # Templates HTML
│   ├── base.html
│   └── restaurante/
│       ├── login.html
│       ├── waiter.html
│       ├── kitchen.html
│       └── admin/
├── static/                  # Arquivos estáticos
├── media/                   # Uploads (logo, imagens de produtos)
├── manage.py
├── requirements.txt
└── initial_data.py          # Script de dados iniciais
```

## 🔧 Tecnologias

- **Backend**: Django 4.2+
- **Frontend**: Bootstrap 5, Bootstrap Icons
- **Banco de Dados**: SQLite (padrão), pode ser alterado para PostgreSQL/MySQL
- **Formulários**: django-crispy-forms com crispy-bootstrap5

## 📝 Customização

### Alterar Cores/Logo

Acesse como gerente: **Configurações** > altere as cores e faça upload do logo.

### Adicionar Produtos

Acesse como gerente: **Cardápio** > **Novo Produto**

### Criar Usuários

Acesse como gerente: **Equipe** > **Novo Membro**

## 🐛 Problemas Comuns

### Erro de migração
```bash
python manage.py makemigrations
python manage.py migrate --run-syncdb
```

### Senha esquecida
```bash
python manage.py changepassword gerente
```

### Resetar banco de dados
```bash
del db.sqlite3
python manage.py migrate
python manage.py shell
# Cole o initial_data.py
```

## 📄 Licença

Projeto desenvolvido para fins educacionais.

---

## 🏗️ Arquitetura Profissional LAN (Restaurante)

Para uso real diário em restaurante, a recomendação é:

- **Django** (negócio e interfaces)
- **Waitress** (HTTP WSGI)
- **Daphne + Django Channels** (WebSocket/tempo real)
- **Redis** (pub/sub Channels)
- **PostgreSQL** (banco principal)
- **Nginx** (reverse proxy para HTTP + WS)

### Fluxo recomendado

- Navegador (garçom/cozinha/gerente) → `Nginx`
- Rotas HTTP → `Waitress` (`nabandeja_project.wsgi`)
- Rotas `/ws/` → `Daphne` (`nabandeja_project.asgi`)
- Eventos em tempo real → `Redis`
- Persistência de dados → `PostgreSQL`

## ⚙️ Deploy no Windows (servidor local)

### 1) Configurar variáveis

Copie `.env.example` para `.env` e ajuste valores.

### 2) Instalar dependências

```bash
pip install -r requirements.txt
```

### 3) Migrar banco

```bash
python manage.py migrate
```

### 4) Iniciar pelo launcher

Use:

- `deploy/windows/start_system.bat`

Ou direto:

```bash
python deploy/windows/launcher.py
```

### 5) Gerar executável

```powershell
powershell -ExecutionPolicy Bypass -File deploy/windows/build_exe.ps1
```

Saída esperada:

- `dist/NaBandeja.exe`

## 📡 Recursos em Tempo Real

## 🛡️ Banco Seguro Por Anos (recomendado)

Para durabilidade real de longo prazo, siga esta ordem:

1. Use PostgreSQL em produção sempre que possível (`DB_ENGINE=postgres`).
2. Tenha backups automáticos frequentes com retenção.
3. Mantenha uma cópia fora da máquina principal (outro disco/servidor/nuvem).
4. Teste restauração periodicamente (não basta só gerar backup).

### Backup para PostgreSQL

Scripts prontos:

- `deploy/windows/backup_postgres.ps1`
- `deploy/windows/schedule_db_backup_task.ps1`

Exemplo de agendamento:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/windows/schedule_db_backup_task.ps1 -EveryMinutes 30
```

### Backup para SQLite

Se ainda estiver usando SQLite, agora há script dedicado com cópia consistente e checksum SHA-256:

- `deploy/windows/backup_sqlite.ps1`
- `deploy/windows/schedule_sqlite_backup_task.ps1`

Exemplo de execução manual:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/windows/backup_sqlite.ps1
```

Exemplo de agendamento:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/windows/schedule_sqlite_backup_task.ps1 -EveryMinutes 30
```

### Observação de segurança importante

O script `deploy/windows/auto_backup_git_push.ps1` foi ajustado para **não** commitar o banco vivo por padrão.
Isso reduz risco de exposição de dados sensíveis no histórico Git.

O sistema implementa WebSocket para atualizações em tempo real em todas as telas principais.

**Páginas com atualização automática:**
- **Dashboard do Gerente** (`/admin/dashboard/`): Stats, pedidos ativos, alertas de estoque
- **Cozinha** (`/kitchen/`): Novos pedidos aparecem instantaneamente
- **Garçom** (`/waiter/`): Mesas ativas sincronizadas em tempo real

**WebSocket Endpoint:**
- `/ws/orders/`

**Eventos publicados:**
- `order.created`: Novo pedido criado
- `order.updated`: Pedido modificado
- `order.status_changed`: Status alterado
- `order.deleted`: Pedido cancelado

**Sistema de notificações:**
- Toast messages para feedback visual instantâneo
- Indicador de status da conexão em tempo real
- Reconexão automática com exponential backoff

**📚 Documentação completa:** [docs/REALTIME_FEATURES.md](docs/REALTIME_FEATURES.md)

**Requisitos:**
- Redis rodando: `redis-server`
- Daphne ASGI server: `daphne -p 8001 nabandeja_project.asgi:application`
- `ENABLE_REALTIME=True` no `.env`

## 📱 PWA

Recursos adicionados:

- Manifest: `/manifest.webmanifest`
- Service Worker: `/sw.js`
- Ícones: `static/pwa/`

Nos celulares, abra o sistema e use **Adicionar à tela inicial**.

## 🔒 Segurança recomendada

- `DJANGO_DEBUG=false` em produção
- `DJANGO_SECRET_KEY` forte
- `DJANGO_ALLOWED_HOSTS` restrito ao IP/hostname LAN
- `DJANGO_CSRF_TRUSTED_ORIGINS` definido com URLs HTTPS reais de produção
- `AUTO_ALLOW_LOCAL_HOSTS=false` em produção
- Usuários separados por função e senhas fortes
- Rede operacional separada da rede de clientes

Validação rápida de hardening:

```bash
python manage.py security_audit
```

O comando executa `check --deploy` do Django e validações adicionais do projeto.

## 💾 Backup automático

Script pronto:

- `deploy/windows/backup_postgres.ps1`

Agendar no Windows Task Scheduler (ex.: diariamente às 03:00).
