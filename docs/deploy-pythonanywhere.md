# NaBandeja no PythonAnywhere (várias lojas)

Um servidor na internet com **várias lojas**, cada uma com o próprio banco de dados, e um
**painel central** só seu para criar, acessar e desativar lojas.

```
https://SEU-USUARIO.pythonanywhere.com/                 login (Empresa + Usuário + Senha)
https://SEU-USUARIO.pythonanywhere.com/central/         painel central (empresa "central")
https://SEU-USUARIO.pythonanywhere.com/l/billa-burguer/ a loja Billá Burger
```

| Quem | Campo Empresa | O que acessa |
|---|---|---|
| Você (dono do servidor) | `central` | Lista de lojas, criar loja, entrar em qualquer loja como suporte |
| Equipe de uma loja | código da loja (ex.: `billa-burguer`) | Só a própria loja |

Como funciona por dentro:

- `central.sqlite3` guarda as lojas e os administradores do servidor.
- Cada loja fica em `lojas/<código>.sqlite3`.
- Uma loja nunca enxerga os dados de outra.
- A sessão de uma loja não vale em outra: se o garçom da loja A abrir um endereço da loja B, ele cai no login da loja B.

> **Diferença para a instalação na loja:** o PythonAnywhere gratuito não tem WebSocket. As telas
> se atualizam sozinhas a cada poucos segundos, em vez de na hora. Todo o resto funciona igual.
> A instalação no PC da loja (rede local, sem internet) continua existindo e não muda nada.

---

## 1. Criar a conta

1. Entre em <https://www.pythonanywhere.com> e crie uma conta **Beginner (grátis)**.
2. O nome de usuário vira o endereço: `SEU-USUARIO.pythonanywhere.com`. Neste guia, troque
   `SEU-USUARIO` pelo seu nome de usuário.

## 2. Baixar o sistema

No PythonAnywhere, abra **Consoles → Bash** e cole:

```bash
git clone https://github.com/niviton/NaBandeja.git ~/NaBandeja
cd ~/NaBandeja
```

> O repositório tem dados de clientes (banco e fotos do Billá). **Mantenha-o privado.**
> Se o `git clone` pedir senha, use um *Personal Access Token* do GitHub
> (GitHub → Settings → Developer settings → Personal access tokens → Fine-grained,
> com acesso de leitura ao repositório NaBandeja). Cole o token no lugar da senha.

## 3. Criar o ambiente Python

O Django 6 precisa de **Python 3.12 ou mais novo**:

```bash
mkvirtualenv --python=python3.13 nabandeja
AUTOBAHN_USE_NVX=0 pip install -r requirements.txt
```

O `mkvirtualenv` já ativa o ambiente. Em consoles novos, ative com `workon nabandeja`.
Se o `python3.13` não existir, troque por `python3.12`.

## 4. Configurar (`.env`)

Gere uma chave secreta:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Crie o arquivo de configuração:

```bash
nano ~/NaBandeja/.env
```

Cole o conteúdo abaixo, trocando `SEU-USUARIO` e `COLE-A-CHAVE-AQUI`. Para salvar no nano:
`Ctrl+O`, `Enter`, `Ctrl+X`.

```ini
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=COLE-A-CHAVE-AQUI
DJANGO_ALLOWED_HOSTS=SEU-USUARIO.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://SEU-USUARIO.pythonanywhere.com
AUTO_ALLOW_LOCAL_HOSTS=false
TRUST_X_FORWARDED_PROTO=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true

NABANDEJA_MULTI_LOJA=true
PUBLIC_BASE_URL=https://SEU-USUARIO.pythonanywhere.com
```

## 5. Preparar o banco central e o seu acesso

```bash
cd ~/NaBandeja
python manage.py migrar_lojas
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

O `createsuperuser` cria **o seu login do painel central**:

- escolha um usuário (ex.: `niviton`);
- informe o seu e-mail;
- crie uma senha **nova e forte**, diferente das que você já usa.

## 6. Criar o site (Web app)

1. Abra a aba **Web → Add a new web app → Next**.
2. Escolha **Manual configuration** (não escolha "Django").
3. Escolha a **mesma versão do Python** do passo 3.
4. Na página do web app, em **Virtualenv**, informe:
   `/home/SEU-USUARIO/.virtualenvs/nabandeja`
5. Em **Code**, clique no link do **WSGI configuration file**, apague todo o conteúdo e cole:

   ```python
   import os
   import sys

   path = '/home/SEU-USUARIO/NaBandeja'
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ['DJANGO_SETTINGS_MODULE'] = 'nabandeja_project.settings'

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

   Salve (**Save**).
6. Em **Static files**, adicione as duas linhas:

   | URL | Directory |
   |---|---|
   | `/static/` | `/home/SEU-USUARIO/NaBandeja/staticfiles` |
   | `/media/` | `/home/SEU-USUARIO/NaBandeja/media` |

7. Em **Security**, ligue **Force HTTPS**.
8. Clique em **Reload** (botão verde, no topo).

Abra `https://SEU-USUARIO.pythonanywhere.com`. Se aparecer um erro, veja o **Error log**
na aba Web (o link fica na seção *Log files*).

## 7. Criar a primeira loja

1. Entre com **Empresa** `central`, o usuário e a senha criados no passo 5.
2. Clique em **Nova loja** e informe:
   - o nome;
   - o código (vai no endereço e no login, ex.: `pizzaria-do-joao`);
   - o usuário e a senha inicial do gerente.
3. Mande para o gerente:
   - o endereço `https://SEU-USUARIO.pythonanywhere.com`;
   - a **Empresa** (o código da loja);
   - o usuário e a senha.

   No primeiro acesso, o gerente vê o assistente de primeiro uso (loja, PIX, mesas, cardápio).
4. **Entrar como suporte** abre a loja com o usuário de suporte. De lá dá para:
   - ligar e desligar módulos (Gestão → Suporte NaBandeja);
   - redefinir senhas;
   - ver relatórios.

   Para voltar ao painel central, clique em **Sair** e entre de novo com a empresa `central`.
5. **Desativar** bloqueia a entrada de todos da loja, sem apagar nada. **Reativar** devolve o acesso.

Também dá para criar loja pelo console:

```bash
python manage.py criar_loja "Pizzaria do João" pizzaria-do-joao gerente SenhaInicialForte123
```

### Importar um cardápio pronto

A pasta `cardapios/` tem cardápios prontos (categorias, produtos, preços, descrições, nome e logo
da loja). Para carregar um deles numa loja:

```bash
python manage.py importar_cardapio cardapios/billa-burger.json --loja billar
python manage.py importar_cardapio cardapios/dogao-canaa.json --loja canaa
```

- Pode rodar de novo: atualiza preço e descrição pelo nome do produto e nunca apaga nada.
- Os produtos entram com estoque 999. Ajuste em *Gestão → Produtos* o que precisar controlar
  (ex.: bebidas).
- Para um cliente novo, copie um dos arquivos, troque os itens e importe.

## 8. Backup diário

Na aba **Tasks**, crie uma tarefa diária (o plano grátis permite uma) com o comando:

```bash
/home/SEU-USUARIO/.virtualenvs/nabandeja/bin/python /home/SEU-USUARIO/NaBandeja/manage.py backup_lojas
```

As cópias ficam em `~/NaBandeja/backups/auto/<código-da-loja>/`. Para baixar uma cópia,
use a aba **Files**.

## 9. Atualizar o sistema

Depois de cada atualização no GitHub, no console Bash:

```bash
workon nabandeja
cd ~/NaBandeja
git pull
AUTOBAHN_USE_NVX=0 pip install -r requirements.txt
python manage.py migrar_lojas
python manage.py collectstatic --noinput
```

Depois clique em **Reload** na aba Web.

## Cuidados

- **Conta grátis:** entre no PythonAnywhere pelo menos **uma vez a cada 3 meses** e clique em
  *"Run until 3 months from today"* na aba Web. Senão, o site é desligado.
- **Espaço:** o plano grátis tem 512 MB. Cada loja começa com cerca de 0,5 MB. As fotos dos
  produtos e os backups são o que mais ocupa espaço.
- **Login com Google:** fica desligado no modo várias lojas. Use empresa, usuário e senha.
- **QR Codes:** com o `PUBLIC_BASE_URL` configurado, os QR das mesas e do cardápio já saem com o
  endereço público da loja (`.../l/<código>/...`).

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `DisallowedHost` no Error log | `DJANGO_ALLOWED_HOSTS` diferente do endereço do site |
| `Defina DJANGO_SECRET_KEY` | O `.env` não está em `~/NaBandeja/.env` ou a chave está vazia |
| Página sem estilo (sem cores) | Faltou o `collectstatic` ou o mapeamento `/static/` |
| Erro 403 CSRF ao entrar | Falta `https://` em `DJANGO_CSRF_TRUSTED_ORIGINS` |
| "Loja não encontrada" | Código errado no endereço ou loja desativada no painel central |
