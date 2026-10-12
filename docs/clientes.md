# Clientes

O código é **um só** para todos os clientes (branch `main`). O que muda de uma loja para outra (nome, logo, cores, cardápio, módulos) fica no **banco de cada loja**, nunca no código.

Os clientes são criados e acompanhados pelo **[painel master](master.md)**:

| O quê | Onde |
|---|---|
| Código do sistema | Repositório `NaBandeja` (branch `main`), sem dados de clientes |
| Dados de cada loja | No PC da loja + backup criptografado no repositório privado `nabandeja-dados-<código>` |
| Cadastro das lojas, chaves e instaladores | Painel master, só no seu PC |

## Criar um cliente

**Painel master › Nova empresa.** Veja [master.md](master.md#criar-uma-empresa).

## Levar melhorias para os clientes

Toda melhoria é feita na `main`. No PC de cada loja:

```powershell
git pull
.\deploy\windows\start_system.bat
```

As migrações novas são aplicadas ao iniciar, sem apagar nada. O banco, as fotos, o `.env` e a chave de envio não estão no git, então o `pull` não mexe neles.

## Regras

- **Nunca** faça commit de `db.sqlite3`, `media/`, `.env` ou `chave-backup`: o `.gitignore` já impede.
- O que for diferente entre clientes deve ser **configuração** (tela Configurações, módulos do suporte ou `.env`), nunca um `if cliente == ...` no código.

## Clientes do modelo antigo (uma branch por cliente)

Antes, cada cliente tinha uma branch `cliente/<slug>` com o `db.sqlite3` **sem criptografia** dentro do repositório do código. Para migrar um desses clientes:

1. No painel master, crie a empresa **importando** o `db.sqlite3` atual da loja.
2. Gere o instalador e extraia no PC da loja (ele traz o `.env` com o backup novo).
3. No PC da loja, troque para a `main`: `git switch main`.
4. Depois que o primeiro backup novo chegar ao painel, **apague a branch antiga do GitHub**. O histórico dela ainda contém o banco sem criptografia:
   ```powershell
   git push origin --delete cliente/<slug>
   ```
