# Outros ambientes: Termux, Railway, VPS e PythonAnywhere

O código é o mesmo em todos. Muda só **como subir** e **quais dependências** instalar:

| Ambiente | Dependências | Servidor | Tempo real |
|---|---|---|---|
| PC Windows da loja | `requirements.txt` | `deploy\windows\start_system.bat` | WebSocket |
| Android (Termux) | `requirements/asgi.txt` (ou `base.txt`) | `python -m nabandeja_project.servir` | WebSocket (ou polling) |
| Railway | `requirements/asgi.txt` + `postgres.txt` | `Procfile` | WebSocket |
| VPS (Linux) | `requirements/asgi.txt` (+ `postgres.txt`, `redis.txt`) | systemd + `servir` | WebSocket |
| PythonAnywhere | `requirements/base.txt` | WSGI do painel deles | polling |

O `servir` usa o **Daphne** (ASGI, páginas e WebSocket na mesma porta) quando ele está instalado. Sem ele, sobe o servidor WSGI do próprio Django, com threads, e o tempo real passa a usar polling. Detalhes do tempo real: [tempo-real.md](tempo-real.md).

Em todos os ambientes, crie o `.env` a partir do `.env.example` (no mínimo `DJANGO_SECRET_KEY` e `DJANGO_ALLOWED_HOSTS`).

## Android com Termux (ex.: Galaxy S21)

Instale o Termux pelo **F-Droid** (a versão da Play Store está desatualizada).

```bash
pkg update && pkg upgrade
pkg install python git python-cryptography python-pillow
git clone https://github.com/niviton/nabandeja.git && cd nabandeja
pip install -r requirements/asgi.txt     # se o twisted não instalar: pip install -r requirements/base.txt
cp .env.example .env && nano .env        # DJANGO_SECRET_KEY e DJANGO_ALLOWED_HOSTS=IP-do-celular,localhost
python manage.py migrate
python manage.py ensure_initial_access   # mostra a senha do gerente
python -m nabandeja_project.servir
```

- Os outros aparelhos acessam por `http://IP-DO-CELULAR:8000` na mesma rede Wi-Fi.
- Para o Android não matar o servidor: `termux-wake-lock` e desligue a economia de bateria para o Termux.
- `cryptography` e `pillow` vêm do `pkg` porque compilar no celular é lento ou falha.

## Railway

1. Novo projeto a partir do repositório e um banco **PostgreSQL** (o Railway cria a `DATABASE_URL`).
2. Variáveis do serviço:
   ```env
   DJANGO_SECRET_KEY=...
   # REDIS_URL=...  (só com mais de uma réplica; acrescente channels-redis às dependências)
   ```
   O `requirements.txt` padrão já traz Daphne, Channels e o driver do PostgreSQL.
3. O `Procfile` já sobe tudo: `web: python -m nabandeja_project.servir --migrate`. Ele lê a `PORT` do Railway.

O domínio público (`RAILWAY_PUBLIC_DOMAIN`) entra sozinho em `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`, e o HTTPS do proxy é reconhecido.

> Fotos enviadas (`media/`) ficam no disco do container: use um **volume** do Railway montado em `/app/media`.

## VPS (Linux)

```bash
python3 -m venv venv && venv/bin/pip install -r requirements/asgi.txt -r requirements/postgres.txt
venv/bin/python manage.py collectstatic --noinput
```

`/etc/systemd/system/nabandeja.service`:

```ini
[Service]
WorkingDirectory=/srv/nabandeja
EnvironmentFile=/srv/nabandeja/.env
ExecStart=/srv/nabandeja/venv/bin/python -m nabandeja_project.servir --migrate --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Na frente, um Nginx com HTTPS repassando também o WebSocket (`proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`) e `TRUST_X_FORWARDED_PROTO=true` no `.env`.

## PythonAnywhere (só WSGI)

1. Console Bash:
   ```bash
   git clone https://github.com/niviton/nabandeja.git && cd nabandeja
   mkvirtualenv nabandeja --python=python3.12
   pip install -r requirements/base.txt
   cp .env.example .env    # DJANGO_ALLOWED_HOSTS=seu-usuario.pythonanywhere.com
   python manage.py migrate && python manage.py collectstatic --noinput && python manage.py ensure_initial_access
   ```
2. Aba **Web**, em *Manual configuration*: virtualenv `nabandeja` e *Static files* `/static/` → `/home/seu-usuario/nabandeja/staticfiles`.
3. Arquivo WSGI do painel:
   ```python
   import sys
   sys.path.insert(0, '/home/seu-usuario/nabandeja')
   from nabandeja_project.wsgi import application  # noqa
   ```

O `wsgi.py` avisa o sistema que não há WebSocket: as telas usam polling sem tentar conectar.
