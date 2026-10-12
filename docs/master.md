# Painel master

O painel master é a tela do **dono do NaBandeja**. Ele roda só no seu PC e serve para:

- criar empresas (cada uma com banco, gerente e módulos próprios);
- acompanhar todas elas: situação do backup, vendas e pedidos dos últimos 30 dias;
- **entrar** em qualquer empresa para ver ou configurar;
- gerar o **instalador** de cada loja (ou de reinstalação, a partir do último backup).

Cada loja continua rodando **no PC dela**, sem depender de internet. O painel acompanha as lojas pelos backups criptografados que elas enviam.

## Como os dados ficam protegidos

```
PC da loja ──(backup criptografado)──► repositório PRIVADO da loja ──► painel master (abre e mostra)
```

| Peça | Onde fica | O que consegue fazer |
|---|---|---|
| Chave mestra (`backup-privada.pem`) | Só no seu PC, em `NaBandejaMaster\chaves\` | **Abrir** os backups de todas as lojas |
| Chave pública | No `.env` de cada loja | Só **cifrar** o backup (não abre nada) |
| Chave de envio (`chave-backup`) | No PC de cada loja | Só **enviar** para o repositório **daquela** loja |
| Repositório `nabandeja-dados-<código>` | GitHub, privado, um por loja | Guarda o último backup e um por dia (14 dias) |

Mesmo que alguém pegue o PC de uma loja ou acesse o GitHub, não lê os dados de nenhuma loja, e não alcança as outras lojas. O código do sistema fica em outro repositório e nunca recebe dados de clientes.

> ⚠️ **Faça uma cópia da chave mestra** (pendrive guardado e cofre de senhas). Sem ela, **nenhum backup pode ser aberto**, nem para reinstalar uma loja.

## Instalar o painel no seu PC

1. Tenha o sistema instalado normalmente (`deploy\windows\start_system.bat` cria o `venv`).
2. Crie o seu acesso (só uma vez):
   ```powershell
   $env:NABANDEJA_MODO = "master"
   venv\Scripts\python manage.py migrate
   venv\Scripts\python manage.py admin_master --email voce@exemplo.com
   ```
3. Abra com **`INICIAR_MASTER.bat`**. O endereço é http://127.0.0.1:8100 e só este PC acessa. Entre com e-mail e senha (sem empresa).

Tudo do master fica em `%USERPROFILE%\NaBandejaMaster` (fora da pasta do código): `.env`, `master.sqlite3`, chaves e as empresas.

## Ligar o GitHub (repositórios de backup)

1. No GitHub: **Settings › Developer settings › Fine-grained tokens › Generate new token**.
   - *Repository access*: **All repositories** (o painel cria um repositório por loja).
   - *Permissions › Repository*: **Administration: Read and write** (criar repositório e cadastrar a chave da loja) e **Contents: Read and write** (enviar e ler os backups).
2. Edite `%USERPROFILE%\NaBandejaMaster\.env`:
   ```env
   NABANDEJA_GITHUB_OWNER=seu-usuario-ou-organizacao
   NABANDEJA_GITHUB_TOKEN=github_pat_...
   ```
3. Reinicie o `INICIAR_MASTER.bat`.

Sem GitHub, dá para usar uma pasta (disco externo ou de rede) com `NABANDEJA_REPOS_DIR=D:\Backups\NaBandeja`. Nesse caso, a loja precisa enxergar essa pasta.

## Criar uma empresa

**Painel › Nova empresa**: nome, código de login, usuário e senha do gerente e módulos. O painel:

1. cria o banco da empresa e o gerente;
2. cria o repositório privado `nabandeja-dados-<código>` e a chave de envio da loja (deploy key);
3. envia o primeiro backup, criptografado.

Para trazer uma loja que **já usa** o NaBandeja, envie o `db.sqlite3` dela no campo "Importar banco existente".

Enquanto a empresa está **em implantação**, "Entrar na empresa" abre o sistema dela para você configurar (cardápio, mesas, PIX, equipe). Ao terminar, clique em **Enviar implantação**.

## Instalar na loja

1. Na empresa, clique em **Gerar instalador**. O zip traz `.env`, chave de envio, banco e fotos.
2. No PC da loja: instale **Git** e **Python 3.12+**, copie a pasta do sistema e extraia o zip dentro dela (ao lado do `manage.py`).
3. Rode `deploy\windows\start_system.bat`.

O zip contém segredos. Leve em pendrive ou por canal privado e apague depois.

A partir daí a loja envia sozinha um backup **a cada hora**, e também quando o gerente clica em **Salvar dados** no rodapé. Quando o primeiro backup da loja chega, a empresa fica **Ativa** no painel. Daí em diante, "Entrar" abre uma **cópia somente leitura** do último backup, porque os dados de verdade estão na loja.

## Acompanhar e restaurar

- **Atualizar do Git** busca o último backup de cada loja e atualiza os números.
- **Backup atrasado**: a loja não envia há mais de 2 dias (PC desligado, sem internet ou erro). O erro aparece no rodapé do sistema da loja e em Gestão › Sistema.
- **Pontos de restauração**: um backup por dia (14 dias). "Abrir" troca a cópia usada em "Entrar" e no instalador.
- **PC da loja quebrou**: gere o instalador (ele usa o último backup) e instale num PC novo.

## Arquivos

| Arquivo | Papel |
|---|---|
| `restaurante/services/master.py` | Empresas, repositórios, instalador |
| `restaurante/services/backup_remoto.py` | Envio e busca dos backups (git) |
| `restaurante/services/cofre.py` | Criptografia e chaves |
| `restaurante/services/espelho.py` | "Entrar na empresa" (um processo por empresa) |
| `restaurante/views/master.py`, `templates/master/` | Telas do painel |
