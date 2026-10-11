# Segurança

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste. O `.env` **nunca** vai para o Git.

| Variável | Produção | Descrição |
|---|---|---|
| `DJANGO_SECRET_KEY` | **obrigatória** | Chave longa e aleatória. Sem ela o sistema não inicia. Gerada sozinha no primeiro início. |
| `DJANGO_DEBUG` | `false` (padrão) | `true` apenas em desenvolvimento. |
| `DJANGO_ALLOWED_HOSTS` | IPs/hostnames da rede | Ex.: `localhost,127.0.0.1,192.168.1.100` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | URLs reais de acesso | Ex.: `https://192.168.1.100` |
| `AUTO_ALLOW_LOCAL_HOSTS` | `true` | Libera o IP e o nome do PC na rede local (mudam com o roteador). |
| `USE_HTTPS` | `true` com certificado | Liga redirecionamento para HTTPS e cookies seguros. |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS` | `5`, `300` | Bloqueio após senhas erradas. |
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
- [ ] Senha do `gerente` trocada e um usuário por pessoa, com o papel certo (garçom, cozinha, gerente)
- [ ] Rede do sistema separada do Wi-Fi dos clientes, se possível
- [ ] Backup automático ativo ([Backup](backup.md))
- [ ] Repositório **privado** no GitHub

## O que o sistema já faz

- **Bloqueio de login:** após 5 senhas erradas, o usuário fica bloqueado por 5 minutos naquele aparelho.
- **Histórico protegido:** produtos, categorias, ingredientes e usuários com histórico são **desativados**, não apagados.
- **Auditoria:** fechamento e cancelamento de conta, caixa, configurações e equipe ficam registrados (Django Admin > Logs de Auditoria).
- **Logs de erro** em `logs/nabandeja.log`, com rotação automática.

## Auditoria

```bash
python manage.py security_audit
```

O comando roda o `check --deploy` do Django e as validações extras do NaBandeja.
