# Desenvolvimento

## Ambiente

```powershell
python -m venv venv
$env:AUTOBAHN_USE_NVX = "0"
venv\Scripts\pip install -r requirements-dev.txt
"DJANGO_DEBUG=true" | Out-File -Encoding utf8 .env
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py runserver
```

Para testar sem mexer no banco do cliente: `SQLITE_PATH=C:\caminho\copia.sqlite3` no `.env`.

## Organização do código

| Pasta | Conteúdo |
|---|---|
| `restaurante/services/` | Regras de negócio (pedidos, estoque, pagamentos, caixa, mesas, PIX, licença, backup, relatórios) |
| `restaurante/views/` | Telas, uma por área (`orders` = salão/cozinha/conta, `manager`, `operations`, `finance`, `system`, `public`) |
| `restaurante/permissions.py` | `@role_required('gerente')` etc. |
| `templates/app/` | Telas da equipe; arquivos com `_` são fragmentos atualizados pelo htmx |
| `templates/public/` | Cardápio digital e pedido online |
| `static/js/nabandeja.js` | Tempo real (WebSocket com polling de reserva), sons e avisos |

Regra: **views só traduzem a requisição para os serviços**. Erros de regra viram `OrderError` com a mensagem para o usuário.

## CSS (Tailwind)

As classes são compiladas em `static/css/app.css` (versionado). Depois de usar classes novas nos templates:

1. Baixe uma vez o executável: https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-windows-x64.exe e salve como `tools\tailwindcss.exe`.
2. Rode `scripts\build_css.bat`.

## Testes e qualidade

```powershell
venv\Scripts\python manage.py test restaurante
venv\Scripts\python -m pyflakes restaurante nabandeja_project scripts
```

O GitHub Actions roda tudo a cada push.
