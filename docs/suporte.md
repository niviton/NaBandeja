# Suporte NaBandeja (superusuário)

Cada loja tem a própria instalação. Você (dono do NaBandeja) tem um usuário de suporte em cada uma, com acesso a tudo e a uma página exclusiva: **Suporte NaBandeja**.

## Login das lojas

A tela inicial pede três campos:

| Campo | Exemplo |
|---|---|
| **Empresa** | `billa-burger` (acentos, espaços e maiúsculas não importam) |
| **Usuário** | `ana` |
| **Senha** | a senha da pessoa |

O campo empresa fica guardado no aparelho depois do primeiro login. O código de cada loja é definido na página de suporte (e o `novo_cliente.py` já cria com o nome da branch).

## Criar o seu usuário de suporte

A mesma senha em todas as lojas. Para não deixar a senha escrita no PC do cliente, use o **hash** dela:

```powershell
# 1. Uma vez, no seu computador: gera o hash (pede a senha, mínimo 12 caracteres)
venv\Scripts\python.exe manage.py suporte_nabandeja --gerar-hash

# 2. Em cada loja: cria/atualiza o usuário "nabandeja" com esse hash
venv\Scripts\python.exe manage.py suporte_nabandeja --hash "<hash gerado>"
```

Ou coloque no `.env` da loja `NABANDEJA_SUPPORT_HASH=<hash>`: o sistema cria o usuário sozinho ao iniciar. O `novo_cliente.py` também usa essa variável, se existir no seu terminal.

Login: empresa da loja, usuário **`nabandeja`** e a sua senha.

## O que o suporte faz

Em **Painel → Suporte NaBandeja**:

- **Código da empresa** usado no login.
- **Módulos** do cliente (desligado: some do menu e as telas não abrem; os dados ficam guardados):
  Delivery · Pedidos online · Cardápio digital · Estoque por ingredientes · Caixa · Contas a pagar · PIX no cupom · Login com Google.
- **Licença**: instalar a licença emitida com `scripts/licenca.py` (veja [licenca.md](licenca.md)).
- **Senhas da equipe**: gerar uma senha nova para quem esqueceu.

O usuário de suporte não aparece na lista **Equipe** da loja e o gerente não consegue editá-lo nem desativá-lo. O `/admin/` técnico do Django também fica restrito ao suporte.
