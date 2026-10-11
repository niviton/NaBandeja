# Instalação

## Opção 1: Instalação automática (Windows)

Requisitos: [Python 3.11+](https://www.python.org/downloads/) e [Git](https://git-scm.com/downloads).

```powershell
git clone https://github.com/niviton/nabandeja.git
cd nabandeja
.\INICIAR_PC_NOVO.bat
```

O script faz o seguinte:

1. cria o ambiente virtual (`venv`);
2. instala as dependências do `requirements.txt`;
3. aplica as migrações do banco;
4. cria o usuário `gerente`, se ainda não existir;
5. cria ou atualiza o atalho na Área de Trabalho ([detalhes](deploy-windows.md#atalho-na-área-de-trabalho));
6. inicia o servidor e abre o navegador.

Para um cliente específico, troque para a branch dele antes de iniciar:

```powershell
git switch cliente/billa-burguer
.\INICIAR_PC_NOVO.bat
```

## Opção 2: Instalação manual

```bash
python -m venv venv
venv\Scripts\activate          # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # depois ajuste os valores
python manage.py migrate
python manage.py ensure_initial_access
python manage.py runserver 0.0.0.0:8000
```

Endereços de acesso:

- **No próprio PC:** http://localhost:8000
- **Em celulares e tablets da mesma rede:** `http://IP_DO_COMPUTADOR:8000` (o IP aparece no `ipconfig` e na tela **Configurações**)

> Para desenvolvimento local, coloque `DJANGO_DEBUG=true` e `DB_ENGINE=sqlite` no `.env`.

## Opção 3: Executável `.exe`

Veja [Implantação no Windows](deploy-windows.md#executável-exe).

## Primeiro acesso

O usuário inicial é o **`gerente`**. A senha depende de como ela foi definida:

- **`NABANDEJA_INIT_ADMIN_PASSWORD` definida no `.env`:** é essa senha.
- **Sem a variável, em modo desenvolvimento (`DJANGO_DEBUG=true`):** o sistema gera uma senha aleatória e mostra no terminal.
- **Cliente criado com `novo_cliente.py`:** a senha aparece na tela ao final do script.

Para trocar a senha:

```bash
python manage.py changepassword gerente
```

Depois de entrar, use estas telas:

1. **Configurações:** nome da loja, logo, cores, dados para o cupom e chave PIX.
2. **Cardápio:** categorias e produtos.
3. **Equipe:** garçons e cozinha.

### Dados de exemplo

Para popular um banco vazio com configurações e produtos de exemplo:

```bash
python manage.py shell -c "exec(open('scripts/initial_data.py', encoding='utf-8').read())"
```

## Problemas comuns

**"Porta 8000 já está em uso"**

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Não consigo acessar pelo celular**

1. Confirme que o celular está na mesma rede Wi-Fi.
2. Libere a porta no firewall ([como fazer](deploy-windows.md#rede-local-e-firewall)).
3. Confira o IP com `ipconfig`.

**Erro de migração**

```bash
python manage.py migrate
```

**Recomeçar com o banco vazio (apaga todos os dados!)**

```powershell
del db.sqlite3
python manage.py migrate
python manage.py ensure_initial_access
```
