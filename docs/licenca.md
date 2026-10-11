# Licenças (uso do dono do NaBandeja)

Cada cliente recebe uma licença com data de validade, assinada digitalmente. O sistema confere a assinatura sem internet.

| Situação | O que acontece |
|---|---|
| Sem licença instalada | Funciona normalmente. |
| Faltam 10 dias ou menos | Aviso para o gerente. |
| Vencida há até 7 dias | Aviso em vermelho (tolerância). |
| Vencida há mais de 7 dias | **Novos pedidos são bloqueados**; contas abertas ainda podem ser fechadas. |

## Chave privada

Fica em `%USERPROFILE%\.nabandeja\licenca_privada.pem`, **fora do repositório**. Faça backup (pendrive, cofre de senhas). Sem ela não dá para emitir licenças; se vazar, qualquer pessoa emite.

## Emitir

```powershell
venv\Scripts\python.exe scripts\licenca.py emitir --cliente "Billá Burger" --slug billa-burguer --dias 365
venv\Scripts\python.exe scripts\licenca.py emitir --cliente "Bar do Zé" --slug bar-do-ze --ate 2027-12-31
```

O cliente cola a licença em **Sistema → Licença**. Uma licença nova só é aceita se vencer depois da atual.

Para conferir uma licença: `python scripts\licenca.py ver <licença>`.
