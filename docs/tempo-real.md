# Tempo real e PWA

## Atualização em tempo real

As telas principais se atualizam sozinhas, sem recarregar a página:

| Tela | O que atualiza |
|---|---|
| **Painel do gerente** | Vendas do dia, pedidos ativos, mesas ocupadas, alertas de estoque |
| **Cozinha** | Pedidos novos aparecem na hora |
| **Garçom** | Status das mesas e dos pedidos |

### Como funciona

- **WebSocket** em `/ws/orders/`, servido pelo Daphne e pelo Django Channels.
- A camada de canais é **em memória** (`InMemoryChannelLayer`), então não precisa de Redis.
- Se o WebSocket cair, o navegador **reconecta** com espera crescente e, enquanto isso, usa **polling HTTP**. No executável `.exe` o polling é sempre usado.
- Um indicador na tela mostra o estado da conexão, e avisos rápidos (toasts) informam os eventos.

### Eventos

| Evento | Quando acontece |
|---|---|
| `order.created` | Um pedido novo é criado |
| `order.updated` | Um pedido é alterado |
| `order.status_changed` | O status de um pedido muda |
| `order.deleted` | Um pedido é cancelado |

O código fica em [`restaurante/realtime.py`](../restaurante/realtime.py) (publicação) e [`restaurante/consumers.py`](../restaurante/consumers.py) (WebSocket).

### Configuração

```env
ENABLE_REALTIME=true
ASGI_PORT=8001
```

## PWA (app no celular)

O sistema pode ser instalado como app:

1. Abra o sistema no Chrome do celular.
2. Toque em **⋮** e depois em **Adicionar à tela inicial**.

O nome e as cores do app vêm das **Configurações** da loja, então cada cliente vê a sua própria marca.

| Arquivo | Caminho |
|---|---|
| Manifest | `/manifest.webmanifest` ([template](../templates/pwa/manifest.webmanifest)) |
| Service worker | `/sw.js` ([template](../templates/pwa/sw.js)) |
| Ícones | [`static/pwa/`](../static/pwa/) |
