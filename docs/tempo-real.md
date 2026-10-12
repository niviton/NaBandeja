# Tempo real e PWA

## Atualização em tempo real

As telas principais se atualizam sozinhas, sem recarregar a página:

| Tela | O que atualiza |
|---|---|
| **Hoje** (gerente) | Vendas do dia, pedidos ativos, mesas ocupadas, alertas |
| **Delivery** | Pedidos online, cozinha, pronto para sair, na rua (som ao chamar/ficar pronto) |
| **Cozinha** | Pedidos novos aparecem na hora (som de pedido novo) |
| **Salão** | Status das mesas, chamados do cliente (som) |

### Um código, qualquer servidor

Cada mudança vira **um evento com id**, gravado no banco (`RealtimeEvent`) depois que o pedido foi salvo. O transporte é só a forma de entrega:

| Transporte | Como | Onde funciona |
|---|---|---|
| **WebSocket** | `/ws/orders/` (Daphne + Channels): chega na hora | ASGI: PC Windows, VPS, Railway, Termux com Daphne |
| **Polling** | `GET /tempo-real/eventos/?desde=<id>` a cada 4 s (15 s com a aba em segundo plano) | Qualquer servidor, inclusive WSGI (PythonAnywhere) e vários processos |

Os dois entregam **os mesmos eventos**, então sons e avisos funcionam igual nos dois. O navegador guarda o último id: não repete e não perde eventos, nem quando o WebSocket cai e volta. Se ficar fora mais de 15 minutos, a tela recarrega tudo.

### Como o sistema escolhe

| Situação | Transporte |
|---|---|
| Servido por `nabandeja_project.wsgi` (PythonAnywhere, `runserver`) | polling (automático) |
| Servido por `nabandeja_project.asgi` com Channels instalado | WebSocket, com polling de reserva |
| WebSocket não conecta 3 vezes seguidas (proxy que bloqueia) | polling; tenta o WebSocket de novo a cada 5 min |

Não é preciso configurar nada. Para forçar:

```env
REALTIME_TRANSPORT=auto        # auto | websocket | polling | off
REALTIME_POLL_SECONDS=4
ENABLE_REALTIME=true           # false desliga só o WebSocket
REDIS_URL=redis://...          # vários processos/servidores com WebSocket (requirements/redis.txt)
```

Com **vários processos** (mais de um worker no Railway/VPS) e sem `REDIS_URL`, o WebSocket só avisa quem está no mesmo processo. O polling de reserva entrega o resto em poucos segundos. Com Redis, todos recebem na hora.

### Eventos

| Evento | Quando acontece |
|---|---|
| `order.created` | Um pedido novo é criado |
| `order.updated` | Dados do pedido mudam (mesa, cliente, total) |
| `order.items_changed` | Itens entram ou saem do pedido |
| `order.status_changed` | Status muda (cozinha, pronto, finalizado, cancelado) |
| `table.call` / `table.call_resolved` | Cliente chamou o garçom ou pediu a conta pelo QR Code |

| Arquivo | Papel |
|---|---|
| [`restaurante/realtime.py`](../restaurante/realtime.py) | Publicar, registro e escolha do transporte |
| [`restaurante/consumers.py`](../restaurante/consumers.py) | WebSocket |
| [`restaurante/views/realtime.py`](../restaurante/views/realtime.py) | Polling |
| [`static/js/nabandeja.js`](../static/js/nabandeja.js) | Navegador |

Como subir em cada ambiente: [deploy-outros.md](deploy-outros.md).

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
