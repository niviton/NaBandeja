# NaBandeja 🍽️

Sistema modular de gestão para restaurantes, lanchonetes, bares e pizzarias:
pedidos por mesa, cozinha em tempo real, estoque, caixa e relatórios.

O código fica em [`nabandeja/`](nabandeja/). Detalhes técnicos estão em [`nabandeja/README.md`](nabandeja/README.md).

## Como funcionam os clientes

| Branch | O que tem |
|---|---|
| `main` | Produto NaBandeja. Todas as melhorias são feitas aqui. |
| `cliente/<nome>` | Uma por cliente: o código da `main` mais o banco, o logo e as fotos daquele cliente. |

### Criar um cliente novo

```bash
cd nabandeja
python novo_cliente.py "Pizzaria do João"
```

Ou dê duplo clique em `nabandeja/NOVO_CLIENTE.bat`.

O script:
1. cria a branch `cliente/pizzaria-do-joao` a partir da `main`;
2. remove fotos, logos e ícones de outros clientes;
3. cria um banco limpo, com o nome da loja e um usuário `gerente` com senha aleatória (aparece na tela);
4. faz o commit.

### Levar melhorias da main para um cliente

```bash
git switch cliente/pizzaria-do-joao
git merge main
git push
```

### Clientes atuais

- `cliente/billa-burguer` (Billá Burger)
