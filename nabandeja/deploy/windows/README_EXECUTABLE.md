# Sistema de Gestão de Restaurante - Versão Executável

## 📦 Primeiros Passos

Você acabou de extrair o **Sistema de Restaurante** em formato executável para Windows.

## ⚙️ Pré-requisitos

Antes de executar o sistema, certifique-se de ter instalado:

### 1. Redis (Obrigatório para tempo real)

**Opção A - Via Chocolatey (Recomendado):**
```powershell
choco install redis-64
```

**Opção B - Download Manual:**
- Baixe: https://github.com/microsoftarchive/redis/releases
- Instale e inicie o serviço Windows

**Verificar se Redis está rodando:**
```cmd
redis-cli ping
```
Deve retornar: `PONG`

### 2. PostgreSQL (Recomendado para produção)

**Download:**
- https://www.postgresql.org/download/windows/
- Instale e configure senha do usuário `postgres`

**Alternativamente:** O sistema pode usar SQLite (sem instalação necessária), mas com limitações de performance.

### 3. Nginx (Opcional - para proxy reverso)

- Baixe: http://nginx.org/en/download.html
- Configure usando o arquivo em: `nginx.conf` (se fornecido)

## 🚀 Configuração Inicial

### 1. Criar arquivo de configuração

Copie `.env.example` para `.env` e edite:

```env
# Database (escolha um)
DB_ENGINE=postgres          # OU sqlite
POSTGRES_DB=restaurante_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua_senha_aqui
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Security
DJANGO_SECRET_KEY=sua-chave-secreta-longa-e-aleatoria
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,SEU_IP_LOCAL

# Redis
REDIS_URL=redis://localhost:6379/0

# Real-time features
ENABLE_REALTIME=True

# Server
APP_HOST=0.0.0.0
APP_PORT=8000
ASGI_PORT=8001
```

### 2. Executar o sistema

**Duplo clique em:**
```
NaBandeja.exe
```

Ou via terminal:
```cmd
NaBandeja.exe
```

O sistema irá:
1. ✅ Verificar ambiente virtual
2. ✅ Tentar iniciar PostgreSQL (se instalado)
3. ✅ Tentar iniciar Redis (se instalado)
4. ✅ Executar migrações do banco de dados
5. ✅ Iniciar servidor HTTP (Waitress)
6. ✅ Iniciar servidor WebSocket (Daphne)
7. ✅ Abrir navegador automaticamente

## 🌐 Acessando o Sistema

Após iniciar, o sistema estará disponível em:

- **HTTP:** http://localhost:8000
- **WebSocket:** ws://localhost:8001/ws/orders/
- **LAN:** http://SEU_IP_LOCAL:8000 (exemplo: http://192.168.1.100:8000)

## 👤 Login Padrão

Se você iniciou com banco de dados novo, crie o primeiro usuário:

1. Abra um terminal na pasta do executável
2. Execute:
   ```cmd
   NaBandeja.exe shell
   ```
3. No shell Python, cole:
   ```python
   from restaurante.models import User
   User.objects.create_superuser(
       username='admin',
       password='admin123',
       role='gerente'
   )
   exit()
   ```

**Credenciais:**
- Usuário: `admin`
- Senha: `admin123`

## 📁 Estrutura de Pastas

```
NaBandeja/
├── NaBandeja.exe    ← Executável principal
├── .env                        ← Configurações (criar)
├── .env.example               ← Modelo de configuração
├── db.sqlite3                 ← Banco SQLite (se usado)
├── media/                     ← Fotos de produtos
│   ├── products/
│   └── settings/
├── templates/                 ← Templates HTML
├── static/                    ← CSS, JS, ícones
└── README.md                  ← Este arquivo
```

## 🔧 Troubleshooting

### Erro: "Redis not available"

Redis não está instalado ou não está rodando.

**Solução:**
```cmd
# Verificar se Redis está rodando
sc query Redis

# Iniciar serviço Redis
sc start Redis

# Se não estiver instalado
choco install redis-64
```

### Erro: "PostgreSQL connection failed"

PostgreSQL não está rodando ou credenciais incorretas.

**Solução:**
```cmd
# Verificar se está rodando
sc query postgresql-x64-16

# Iniciar serviço
sc start postgresql-x64-16

# OU: Use SQLite no .env
DB_ENGINE=sqlite
```

### Erro: "Port 8000 already in use"

Outro programa está usando a porta.

**Solução:**
```cmd
# Descobrir qual processo está usando a porta
netstat -ano | findstr :8000

# Matar o processo (substitua PID pelo número encontrado)
taskkill /PID 1234 /F

# OU: Mudar a porta no .env
APP_PORT=8080
```

### WebSocket não conecta

Daphne não está rodando ou firewall bloqueando.

**Solução:**
```powershell
# Liberar porta no firewall
New-NetFirewallRule -DisplayName "Django WebSocket" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow

# Verificar se Daphne está rodando
netstat -ano | findstr :8001
```

### Sistema não abre no navegador

O executável iniciou mas navegador não abriu automaticamente.

**Solução:**
Abra manualmente: http://localhost:8000

## 📱 Acesso via Rede Local (LAN)

### Para permitir acesso de tablets/celulares na mesma rede:

1. **Descobrir seu IP local:**
   ```cmd
   ipconfig
   ```
   Procure por "Endereço IPv4" (ex: 192.168.1.100)

2. **Adicionar IP ao .env:**
   ```env
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
   ```

3. **Liberar firewall:**
   ```powershell
   New-NetFirewallRule -DisplayName "Django HTTP" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```

4. **Acessar de outro dispositivo:**
   ```
   http://192.168.1.100:8000
   ```

## 🔄 Atualizações em Tempo Real

O sistema possui atualização em tempo real via WebSocket em:

- ✅ Dashboard do Gerente (estatísticas, pedidos)
- ✅ Cozinha (novos pedidos aparecem instantaneamente)
- ✅ Garçom (mesas ativas sincronizadas)

**Requisito:** Redis deve estar rodando para funcionar.

## 💾 Backup

### Backup do Banco de Dados

**SQLite:**
```cmd
copy db.sqlite3 backup_db_%date%.sqlite3
```

**PostgreSQL:**
```cmd
pg_dump -U postgres -d restaurante_db > backup_%date%.sql
```

### Backup de Fotos/Media

```cmd
xcopy media backup_media\ /E /I /Y
```

## 📞 Suporte

Para problemas técnicos, consulte:
- **Documentação completa:** docs/DEPLOY_WINDOWS_LAN.md
- **Recursos em tempo real:** docs/REALTIME_FEATURES.md
- **README principal:** README.md

## 📄 Licença

Este sistema é fornecido como está, sem garantias.

---

**Sistema de Gestão de Restaurante v2.0**  
Desenvolvido com Django + Channels + WebSocket  
Build: Março 2026
