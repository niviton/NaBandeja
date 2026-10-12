# Clientes

O NaBandeja usa **uma branch do Git por cliente**:

| Branch | Conteúdo |
|---|---|
| `main` | O produto. Toda correção e funcionalidade nova é feita aqui. |
| `cliente/<slug>` | O código da `main` mais os dados do cliente: `db.sqlite3`, logo, fotos dos produtos e ícone do atalho. |

O nome, o logo, as cores e os dados do cupom de cada loja ficam no banco (tela **Configurações**). Por isso o código é o mesmo para todos os clientes e as melhorias da `main` chegam a eles com um `merge`.

## Criar um cliente

Com a `main` atualizada e sem alterações pendentes:

```powershell
git switch main
git pull
python scripts/novo_cliente.py "Pizzaria do João"
```

Se não quiser usar o terminal, dê duplo clique em **`NOVO_CLIENTE.bat`**.

Opções do script:

| Opção | Exemplo | Padrão |
|---|---|---|
| `--slogan` | `--slogan "A melhor pizza do bairro"` | genérico |
| `--cor` | `--cor "#16a34a"` | `#ef4444` |
| `--slug` | `--slug pizzaria-joao` | gerado a partir do nome |
| `--base` | `--base main` | `main` |

O script:

1. cria a branch `cliente/pizzaria-do-joao` a partir da `main`;
2. remove fotos, logos e ícones de outros clientes;
3. cria um banco limpo, com o nome da loja, o **código da empresa** (igual ao slug da branch) e o usuário `gerente`;
4. mostra a **senha do gerente** (anote, ela não fica salva em lugar nenhum);
5. faz o commit.

Para enviar o cliente para o GitHub:

```powershell
git push -u origin cliente/pizzaria-do-joao
```

## Levar melhorias da main para um cliente

```powershell
git switch cliente/pizzaria-do-joao
git merge main
git push
```

Na próxima vez que o sistema iniciar no PC do cliente, as migrações novas são aplicadas sem apagar nada.

Para atualizar todos os clientes de uma vez:

```powershell
git fetch
foreach ($b in git branch --format="%(refname:short)" --list "cliente/*") {
  git switch $b; git merge main --no-edit; git push
}
git switch main
```

## Instalar no PC do cliente

```powershell
git clone -b cliente/pizzaria-do-joao https://github.com/niviton/nabandeja.git
cd nabandeja
.\INICIAR_PC_NOVO.bat
```

## Backup dos dados do cliente

O `db.sqlite3` de cada cliente fica versionado na branch dele. Para salvar o estado atual:

```powershell
git add -f db.sqlite3 media
git commit -m "backup: dados do cliente"
git push
```

Também é possível automatizar isso a cada 30 minutos. Veja [Backup](backup.md#backup-automático-no-git).

> ⚠️ **Privacidade:** o banco tem pedidos, usuários e dados do estabelecimento. Mantenha o repositório **privado** no GitHub.

## Regras para não dar conflito

- **Não altere código direto na branch de um cliente.** Faça na `main` e depois faça o merge.
- **Não faça commit do `db.sqlite3` na `main`.** Ali ele serve só de referência; os dados de verdade ficam nas branches dos clientes.
- O que for diferente entre clientes deve ser uma **configuração** (tela Configurações ou `.env`), nunca um `if cliente == ...` no código.
