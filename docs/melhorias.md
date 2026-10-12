# Checklist de melhorias

Levantamento feito em 11/10/2026, com base no código da versão 2.0.0. Marque `[x]` quando um item for concluído.

**Prioridade:** 🔴 risco de perder dados ou dinheiro · 🟠 importante para vender e dar suporte · 🟡 qualidade do código · 🟢 funcionalidade nova

---

## ✅ Corrigido além do checklist original

- [x] **Caixa contava PIX e cartão como dinheiro na gaveta** — agora só dinheiro em espécie, pela data de pagamento.
- [x] **QR Code do PIX sem valor e dependente de site externo** — agora BR Code oficial com o valor exato, gerado offline.
- [x] **Tempo real nunca conectava** (WebSocket em porta diferente da página) — agora um servidor só, porta 8000.
- [x] **Notificações duplicadas** (gerente recebia 4 cópias de cada evento) e nome de campo errado nas telas.
- [x] **Fechar conta de pedido cancelado** era possível — bloqueado, com forma de pagamento validada.
- [x] **Total do pedido usava preço guardado no carrinho** — agora sempre o preço atual do produto.
- [x] **Plataforma do delivery misturada nas observações** — campo próprio (dados antigos migrados).
- [x] **Redirecionamento aberto** no botão abrir/fechar loja.

## 🔴 Crítico: proteger os dados

- [x] **Apagar um produto apaga o histórico de vendas.** `OrderItem.product` usa `on_delete=CASCADE`. Ao excluir um produto, os itens de pedidos antigos somem e os relatórios ficam errados. Apagar uma categoria leva junto todos os produtos dela.
  - Trocar a exclusão por **desativar** (`is_active=False`).
  - Usar `on_delete=PROTECT` em `OrderItem.product` e `Product.category`.
  - Guardar o **nome do produto** no `OrderItem` no momento da venda.
- [x] **O estoque pode ficar errado com dois garçons ao mesmo tempo.** `Product.stock -= quantidade` é calculado em Python (`models.py:103` e `:117`). Dois pedidos simultâneos podem gravar um valor velho. Trocar por `F('stock') - quantidade` ou `select_for_update()`.
- [x] **`DEBUG` fica ligado por padrão.** Sem `.env`, `DJANGO_DEBUG` vale `true`. No PC do cliente, uma tela de erro mostra código e configuração para qualquer pessoa da rede. O padrão deve ser `false`, e o `INICIAR_PC_NOVO.bat` deve gerar um `.env` com uma `DJANGO_SECRET_KEY` própria.
- [x] **Sem limite de tentativas de login.** Não há proteção contra força bruta na senha. Bloquear por alguns minutos após N tentativas erradas (por exemplo, com `django-axes`).
- [x] **Backup automático ligado por padrão em todo cliente novo.** Hoje é opcional e manual. Resolvido pelo backup externo criptografado (vem pronto no instalador do painel master; roda com o sistema aberto).
- [ ] **Repositório privado no GitHub.** Ele contém o banco do Billá Burger.

## 🟠 Importante: funcionar sempre no restaurante

- [x] **Funcionar sem internet.** `base.html` carrega Tailwind (versão de desenvolvimento, `cdn.tailwindcss.com`), Bootstrap Icons e Google Fonts da internet. Se a internet cair, as telas perdem o visual.
  - Compilar o Tailwind e servir tudo de `static/`.
  - O service worker deve guardar esses arquivos em cache.
- [x] **Fixar as versões das dependências.** `requirements.txt` usa `>=`: hoje instala Django 6.1, mas o projeto foi escrito para 4.2/5.x. Um cliente novo pode receber uma versão incompatível. Gerar `requirements.txt` com versões exatas.
- [x] **Versão do Python.** Neste PC (Python 3.15), o `autobahn`, dependência do WebSocket, só instalou com `AUTOBAHN_USE_NVX=0`. Fixar o Python 3.12 no instalador ou adicionar essa variável ao `start_system.bat`.
- [x] **Tempo real no `.exe`.** O executável não tem WebSocket e usa polling. Avaliar rodar o Daphne também no `.exe`.
- [x] **Atualização do cliente em 1 clique.** Criar um `ATUALIZAR.bat` que faz `git pull`, `pip install` e `migrate`, com backup automático antes.
- [x] **Página de status/diagnóstico** para o suporte: versão, último backup, espaço em disco, IP e se o tempo real está conectado.
- [x] **Log de erros em arquivo.** Não há `LOGGING` configurado. Gravar os erros em `logs/` facilita o suporte remoto.

## 🟡 Qualidade do código

- [x] **Testes automatizados.** Não existe nenhum teste do Django, só uma simulação com Selenium. Começar pelo fluxo crítico: criar pedido → cozinha → fechar conta → caixa → relatório.
- [x] **Dividir o `views.py`** (2.700 linhas, 83 funções) em módulos: `pedidos`, `cozinha`, `caixa`, `cardapio`, `estoque`, `relatorios`, `configuracoes`.
- [x] **Centralizar a checagem de permissão.** `if request.user.role != 'gerente'` se repete 37 vezes. Trocar por um decorator `@role_required('gerente')`.
- [x] **Regras de negócio fora das views.** Total, estoque e fechamento de caixa devem ficar em `services.py` ou nos models, para poderem ser testados.
- [x] **Tratar erros de forma específica.** Há 8 `except Exception` genéricos em `views.py`, que podem esconder bugs.
- [x] **Separar o CSS e o JS dos templates.** `waiter.html` tem 710 linhas, com estilo e script embutidos.
- [x] **CI no GitHub Actions:** rodar `check`, `makemigrations --check` e os testes a cada push.
- [x] **Corrigir a rota `/login/`,** que dá 404 (o login fica em `/`). Útil para links e favoritos.
- [ ] **Ícones do PWA com o logo da loja,** gerados como já é feito com o atalho da Área de Trabalho.

## 🟢 Funcionalidades novas (valor comercial)

### Atendimento
- [x] **Mapa de mesas:** cadastrar mesas e ver livre/ocupada/aguardando conta num grid. Hoje `mesa` é texto livre.
- [x] **Dividir a conta** por pessoa ou por item.
- [ ] ~~**Taxa de serviço (10%)**~~ (fora do escopo, pedido do dono) opcional, com relatório por garçom (comissão).
- [x] **Desconto e cortesia,** com motivo e registro de quem autorizou (já existe `AuditLog`).
- [x] **Transferir ou juntar mesas.**
- [x] **Observações rápidas** por item ("sem cebola", "ao ponto") com botões prontos.

### Cozinha
- [x] **Impressão automática na cozinha/bar** quando o pedido entra, com impressoras separadas por categoria.
- [x] **Tempo de preparo:** cronômetro por pedido e alerta de atraso.
- [x] **Aviso sonoro** de pedido novo e pedido pronto (para o garçom).

### Cliente final
- [x] **Cardápio digital com QR Code na mesa:** o cliente vê o cardápio e chama o garçom.
- [x] **Pedido online / delivery próprio** com link para WhatsApp (a tela `admin-panel/online` já existe).
- [x] **Taxa de entrega** por bairro ou distância.

### Gestão
- [x] **Relatório de lucro:** já existe o custo dos ingredientes (`cost_price`); falta mostrar a margem por produto.
- [x] **Exportar relatórios** em Excel/PDF.
- [x] **Contas a pagar** e fluxo de caixa simples.
- [ ] **Dashboard de vários clientes** para você: vendas e status de cada restaurante (exige servidor central).

### Fiscal e integrações
- [ ] ~~**NFC-e**~~ (fora do escopo por enquanto) (nota fiscal ao consumidor) via API, como Focus NFe ou PlugNotas. É exigência em muitos estados e um grande argumento de venda.
- [ ] **Integração com iFood** (API de pedidos).
- [ ] **PIX com confirmação automática** (API do banco ou Mercado Pago).

### Produto NaBandeja
- [x] **Licença por cliente:** chave de ativação e bloqueio por inadimplência.
- [x] **Assistente de primeiro uso:** após instalar, o sistema pede nome, logo, cores e cardápio inicial.
- [ ] **Site/landing page do NaBandeja** para vender o sistema.
