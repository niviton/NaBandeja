# Login com Google

Com o login com Google, a equipe entra com a própria conta Google e não depende de lembrar a senha. Se alguém esquecer a senha, basta entrar com o Google.

**Regra de segurança:** o Google **não cria contas**. Ele só dá acesso a um usuário que o gerente já cadastrou em **Equipe** com o mesmo e-mail. Uma pessoa de fora com conta Google não consegue entrar.

O serviço é gratuito, mas o PC do sistema precisa de internet no momento do login.

## 1. Criar as credenciais no Google (uma vez)

1. Acesse https://console.cloud.google.com e entre com a sua conta Google.
2. Crie um projeto (ex.: **NaBandeja**).
3. Menu **APIs e serviços → Tela de consentimento OAuth**:
   - Tipo de usuário: **Externo**.
   - Nome do app: **NaBandeja**; e-mail de suporte: o seu.
   - Escopos: deixe os padrão (`email`, `profile`, `openid`).
   - Clique em **Publicar app**. Sem isso, só os e-mails cadastrados como "usuários de teste" conseguem entrar.
4. Menu **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo: **Aplicativo da Web**.
   - Em **URIs de redirecionamento autorizados**, adicione os endereços pelos quais o sistema é acessado (veja o passo 3).
5. Copie o **ID do cliente** e a **Chave secreta do cliente**.

## 2. Configurar o NaBandeja

No arquivo `.env` do PC do sistema:

```env
GOOGLE_CLIENT_ID=123456789-xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
```

Reinicie o sistema. O botão **Entrar com Google** aparece na tela de login.

## 3. Endereços de redirecionamento

O Google só aceita `localhost` ou um **domínio com HTTPS**. Ele **não aceita** endereços de IP como `http://192.168.0.10:8000`.

| Onde vai usar | Endereço de redirecionamento para cadastrar no Google |
|---|---|
| No próprio PC do sistema | `http://localhost:8000/accounts/google/login/callback/` |
| Nos celulares e tablets da rede (com HTTPS) | `https://192.168.0.10.sslip.io/accounts/google/login/callback/` |
| Com domínio próprio | `https://meurestaurante.com.br/accounts/google/login/callback/` |

Troque `192.168.0.10` pelo IP do PC do sistema, que aparece na tela **Configurações**.

**Como funciona nos celulares:**
1. Rode `deploy\windows\setup_ssl.bat` como Administrador. Ele gera um certificado que já inclui o endereço `<ip>.sslip.io`.
2. No `.env`, coloque `USE_HTTPS=true` e reinicie.
3. Nos celulares, acesse `https://192.168.0.10.sslip.io`.

O `sslip.io` é um serviço gratuito que transforma o nome `192.168.0.10.sslip.io` no IP `192.168.0.10`; os dados continuam só na rede local.

> Se o IP do PC mudar, o endereço muda junto. Para evitar isso, fixe o IP do PC no roteador (reserva de DHCP).

## 4. Cadastrar os e-mails da equipe

Em **Equipe**, edite cada membro e preencha o **E-mail** com a conta Google dele. No primeiro login com Google, a conta é vinculada e aparece o selo **Google vinculado**.

## Problemas comuns

| Mensagem | Solução |
|---|---|
| "O e-mail ... não está cadastrado" | Cadastre esse e-mail no membro, em **Equipe**. |
| `redirect_uri_mismatch` (tela do Google) | O endereço usado não está na lista do passo 3. Copie exatamente o que aparece no erro. |
| "Este usuário está desativado" | O gerente desativou o usuário. Reative cadastrando-o de novo. |
| Botão do Google não aparece | Confira `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no `.env` e reinicie. |
