# Backup

Para não perder dados:

1. Faça backups automáticos e frequentes.
2. Guarde uma cópia **fora do PC do estabelecimento**: no GitHub, no Google Drive ou em outro disco.
3. Teste a restauração de vez em quando. Ter o arquivo não basta; é preciso conseguir voltar com ele.

## Backup automático no Git

Esta é a forma recomendada para clientes NaBandeja. A cada 30 minutos, uma cópia do banco vai para a branch do cliente no GitHub.

No PC do cliente, dentro da pasta do sistema:

```powershell
.\deploy\windows\instalar_backup_git_automatico.bat
```

A rotina:

- copia o `db.sqlite3` para `backups\db\`, mantendo as 40 cópias mais recentes;
- faz commit e `git push` para a branch atual (`cliente/<slug>`);
- grava um log em `backups\logs\db_backup_git_push.log`.

Pré-requisitos:

- o repositório precisa estar conectado ao `origin`;
- o `git push` precisa funcionar sem pedir senha (Git Credential Manager ou token salvo).

Para remover a rotina:

```powershell
schtasks /Delete /TN "NaBandeja-DB-Backup-GitPush" /F
```

> ⚠️ O repositório precisa ser **privado**, porque o banco contém dados do estabelecimento.

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
