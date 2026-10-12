# Backup

Para não perder dados:

1. Faça backups automáticos e frequentes.
2. Guarde uma cópia **fora do PC do estabelecimento**: no GitHub, no Google Drive ou em outro disco.
3. Teste a restauração de vez em quando. Ter o arquivo não basta; é preciso conseguir voltar com ele.

## Backup externo criptografado (recomendado)

É a forma padrão para clientes NaBandeja e vem pronta no **instalador gerado pelo [painel master](master.md)**:

- **a cada hora**, com o sistema aberto, e quando o gerente clica em **Salvar dados** no rodapé, o banco e as fotos são **criptografados** e enviados para o repositório privado da loja (`nabandeja-dados-<código>`);
- só a **chave mestra** do painel master consegue abrir. Nem o GitHub, nem quem pegar o PC da loja, lê os dados;
- a chave da loja (`chave-backup`) só escreve no repositório **dela**;
- fica o último backup e **um por dia** dos últimos 14 dias (`BACKUP_REMOTO_DIAS`).

A situação aparece no rodapé (para o gerente) e em **Gestão › Sistema**. Pré-requisito no PC da loja: [Git](https://git-scm.com/downloads) instalado.

Para restaurar ou reinstalar uma loja, use o painel master: **Gerar instalador** sempre usa o último backup ou o ponto de restauração aberto.

> O modelo antigo (commit do `db.sqlite3` na branch do cliente, **sem criptografia**) foi removido. Veja [clientes.md](clientes.md#clientes-do-modelo-antigo-uma-branch-por-cliente) para migrar.

## SQLite: cópia local e Google Drive

[`backup_sqlite.ps1`](../deploy/windows/backup_sqlite.ps1) faz uma cópia consistente do banco, mesmo com o sistema em uso, e gera um checksum SHA-256.

```powershell
# Manual
powershell -ExecutionPolicy Bypass -File deploy\windows\backup_sqlite.ps1

# Agendado a cada 30 minutos
powershell -ExecutionPolicy Bypass -File deploy\windows\schedule_sqlite_backup_task.ps1 -EveryMinutes 30
```

O destino é `C:\Backups\NaBandeja\sqlite`. Se o Google Drive para Desktop estiver instalado, o agendamento usa `Meu Drive\NaBandejaBackups\sqlite`.

## PostgreSQL

```powershell
# Manual
powershell -ExecutionPolicy Bypass -File deploy\windows\backup_postgres.ps1

# Agendado
powershell -ExecutionPolicy Bypass -File deploy\windows\schedule_db_backup_task.ps1 -EveryMinutes 30
```

O destino é `C:\Backups\NaBandeja`, no formato `pg_dump -Fc`.

## Fotos e logos

As imagens enviadas pelo sistema ficam em `media/`. Inclua essa pasta no backup:

```powershell
git add -f media
git commit -m "backup: imagens do cliente"
git push
```

## Restaurar

1. Feche o sistema.
2. Substitua o `db.sqlite3` pela cópia de backup.
3. Inicie de novo. As migrações pendentes são aplicadas automaticamente.
