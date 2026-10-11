 🍽️ NaBandeja - Sistema de Gestão para Restaurantes

## 📋 Opção 1: Usar o Executável Pronto (Recomendado)

### Passo a passo:

1. **Copie a pasta do executável** para o computador:
   ```
   dist\NaBandeja\
   ```

2. **Execute o programa:**
   - Dê duplo clique em `NaBandeja.exe`
   - O navegador abrirá automaticamente

3. **Acesse pelo celular/tablet:**
   - Conecte na mesma rede Wi-Fi
   - Abra o navegador e digite: `http://IP_DO_COMPUTADOR:8000`
   - Para descobrir o IP, no computador execute: `ipconfig`

### ⚠️ Firewall
Se outros dispositivos não conseguirem acessar, libere a porta no firewall (executar como Administrador):
```powershell
New-NetFirewallRule -DisplayName "NaBandeja" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

---

## 📋 Opção 2: Rodar do Código Fonte (Git Clone)

### ✅ Início Automático (PC Novo)

Após clonar, basta executar:

```powershell
INICIAR_PC_NOVO.bat
```

Esse arquivo configura automaticamente no PC novo:
- cria o ambiente virtual (`venv`)
- instala dependências
- aplica migrações do banco
- inicia o sistema na rede local

Depois, na tela **Configurações**, o sistema mostra os links prontos de acesso para PC e celular.

### Requisitos:
- Python 3.11 ou superior: https://www.python.org/downloads/
- Git (opcional): https://git-scm.com/downloads

### Passo a passo:

1. **Clone o repositório:**
   ```powershell
   git clone <URL_DO_REPOSITORIO>
   cd nabandeja
   ```

2. **Instale as dependências:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Execute o sistema:**
   ```powershell
   python manage.py runserver 0.0.0.0:8000
   ```

4. **Acesse no navegador:**
   - No mesmo PC: `http://localhost:8000`
   - Em outro dispositivo: `http://IP_DO_COMPUTADOR:8000`

---

## 📋 Opção 3: Gerar o Executável

Depois de clonar o repositório:

1. **Instale as dependências:**
   ```powershell
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **Gere o executável:**
   ```powershell
   pyinstaller NaBandeja.spec
   ```

3. **O executável estará em:**
   ```
   dist\NaBandeja\NaBandeja.exe
   ```

---

## 🔐 Login Padrão

Na primeira vez, crie um usuário administrador:

1. Acesse o sistema
2. Se não houver usuários, o sistema pedirá para criar
3. Ou pelo terminal:
   ```powershell
   python manage.py createsuperuser
   ```

---

## 📱 Instalar como App no Celular (PWA)

1. Acesse o sistema pelo navegador Chrome
2. Toque nos 3 pontinhos (⋮)
3. Selecione "Adicionar à tela inicial"
4. Pronto! O app aparecerá como um ícone

---

## 🆘 Problemas Comuns

### "Porta 8000 já está em uso"
```powershell
# Descobrir qual programa está usando
netstat -ano | findstr :8000

# Encerrar o processo (substitua XXXX pelo número do PID)
taskkill /PID XXXX /F
```

### "Não consigo acessar pelo celular"
1. Verifique se está na mesma rede Wi-Fi
2. Libere o firewall (comando acima)
3. Verifique o IP com `ipconfig`

### "Executável não abre"
Execute pelo terminal para ver o erro:
```powershell
cd dist\NaBandeja
.\NaBandeja.exe
```

---

## 💾 Backup Automático do Banco no Git (SQLite)

Se quiser salvar o banco automaticamente para não perder dados, use a automação já pronta:

1. Entre na pasta do projeto:
   ```powershell
   cd nabandeja
   ```

2. Instale a tarefa automática (Windows):
   ```powershell
   .\deploy\windows\instalar_backup_git_automatico.bat
   ```

3. O sistema passará a executar a cada 30 minutos:
   - cópia do `db.sqlite3` para `backups\db\`
   - commit automático no Git
   - `git push` para a branch atual

4. Log da automação:
   - `backups\logs\db_backup_git_push.log`

### Pré-requisitos importantes
1. O repositório precisa estar conectado ao remoto (`origin`).
2. O `git push` precisa funcionar sem pedir senha (Git Credential Manager / token já salvo).

### Remover a automação
```powershell
schtasks /Delete /TN "NaBandeja-DB-Backup-GitPush" /F
```

---

## 📁 Estrutura de Arquivos

```
nabandeja/
├── NaBandeja.exe    ← Executável principal
├── manage.py                 ← Script Django (desenvolvimento)
├── requirements.txt          ← Dependências Python
├── db.sqlite3               ← Banco de dados
├── media/                   ← Fotos dos produtos
├── static/                  ← CSS, JS, imagens do sistema
└── templates/               ← Páginas HTML
```

---

**NaBandeja** 🍽️ — sistema modular: cada cliente tem sua própria branch
