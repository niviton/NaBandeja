# Pedidos online e cardápio digital

## Ligar

Em **Configurações → Cardápio digital e pedidos online**:

- **Cardápio digital (QR Code na mesa)**: os QR Codes ficam em **Mesas e QR Code → Imprimir QR Codes**.
- **Aceitar pedidos online**: o link é `http://<ip-do-pc>:8000/pedir/`, mostrado em **Delivery e online**.
- **WhatsApp da loja**: depois de enviar, o cliente vê um botão para confirmar o pedido pelo WhatsApp.
- Cadastre os **bairros e taxas** em **Delivery e online → Bairros e taxas**.

## Como o pedido chega

1. O cliente monta o pedido, informa nome, telefone, endereço e bairro e envia.
2. O pedido aparece em **Delivery e online** como *aguardando confirmação* (e no salão/painel, como alerta).
3. O gerente **aceita** (o estoque é baixado e o pedido vai para a cozinha) ou **recusa**.

Proteções: cada aparelho pode enviar no máximo 3 pedidos a cada 10 minutos; o pedido mínimo é configurável.

## Clientes fora do Wi-Fi da loja (internet)

O NaBandeja roda no computador da loja. Para receber pedidos de quem está em casa, o endereço precisa ser acessível pela internet. Opção gratuita recomendada: **Cloudflare Tunnel**.

1. Crie uma conta grátis em https://dash.cloudflare.com e instale o `cloudflared` no PC da loja.
2. Rode: `cloudflared tunnel --url http://localhost:8000`
3. Ele mostra um endereço `https://xxxx.trycloudflare.com`. Adicione esse domínio em `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` no `.env` e reinicie.

> Para um endereço fixo (ex.: `pedidos.minhaloja.com.br`), use um túnel nomeado com domínio próprio. Expor o sistema na internet também expõe a tela de login: use senhas fortes (o bloqueio após 5 tentativas já está ativo).
