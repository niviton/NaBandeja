# Segurança

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste. O `.env` **nunca** vai para o Git.

| Variável | Produção | Descrição |
|---|---|---|
| `DJANGO_SECRET_KEY` | **obrigatória** | Chave longa e aleatória. Sem ela o sistema não inicia com `DEBUG=false`. |
| `DJANGO_DEBUG` | `false` | `true` apenas em desenvolvimento. |
| `DJANGO_ALLOWED_HOSTS` | IPs/hostnames da rede | Ex.: `localhost,127.0.0.1,192.168.1.100` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | URLs reais de acesso | Ex.: `https://192.168.1.100` |
| `AUTO_ALLOW_LOCAL_HOSTS` | `false` | Libera automaticamente o IP local (prático em desenvolvimento). |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | `true` com HTTPS | |
| `NABANDEJA_INIT_ADMIN_PASSWORD` | **obrigatória** no 1º início | Senha inicial do `gerente`. |
| `DB_ENGINE` | `sqlite` ou `postgres` | |
| `POSTGRES_*` | se usar PostgreSQL | Inclui `POSTGRES_SSLMODE` e os certificados. |

> As variáveis antigas `BILLAR_INIT_ADMIN_*` ainda são aceitas para não quebrar instalações existentes.

Para gerar uma chave secreta:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Checklist de produção

- [ ] `DJANGO_DEBUG=false` e `DJANGO_SECRET_KEY` próprios
- [ ] `DJANGO_ALLOWED_HOSTS` restrito à rede do estabelecimento
- [ ] `AUTO_ALLOW_LOCAL_HOSTS=false`
- [ ] Senha do `gerente` trocada e um usuário por pessoa, com o papel certo (garçom, cozinha, gerente)
- [ ] Rede do sistema separada do Wi-Fi dos clientes, se possível
- [ ] Backup automático ativo ([Backup](backup.md))
- [ ] Repositório **privado** no GitHub

## Auditoria

```bash
python manage.py security_audit
```

O comando roda o `check --deploy` do Django e as validações extras do NaBandeja.
