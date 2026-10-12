# Funcionalidades

O sistema é dividido em **áreas**, sempre na mesma barra no topo (cada pessoa vê só as suas):

| Área | Quem usa | Para quê |
|---|---|---|
| **Hoje** | gerente | Abrir e fechar o dia, caixa, alertas e números do dia |
| **Salão** | garçom, gerente | Mesas e pedidos de balcão |
| **Delivery** | garçom, gerente | Pedidos online e entregas (se o módulo estiver ligado) |
| **Cozinha** | cozinha, gerente | Fila de preparo |
| **Gestão** | gerente | Relatórios, caixas, cardápio, mesas, equipe, configurações |

## O dia da loja (Hoje)

1. **Abrir o dia**: conta o troco da gaveta; abre o caixa e a loja ao mesmo tempo.
2. Durante o dia: vendas, contas fechadas, pedidos em andamento, mesas chamando, pedidos online, estoque baixo e contas a pagar vencendo, tudo numa tela só.
3. **Sangria e suprimento**: retirada ou reforço da gaveta, com motivo. Entram na conferência.
4. **Pausar pedidos**: fecha a loja para pedidos novos sem fechar o caixa.
5. **Reabrir conta** fechada por engano (gerente, com motivo, enquanto o caixa do dia estiver aberto). Os pagamentos dela são estornados.
6. **Fechar o dia**: lista o que ficou aberto (mesas, balcão, entregas, pedidos online), pede a contagem da gaveta e mostra o resumo para imprimir. O histórico fica em *Gestão → Caixas*.

## Salão (garçom)

- **Mapa de mesas** com cores por situação: livre, na cozinha, pronto para servir (pisca), servido, conta pedida.
- **Chamados do cliente** (pelo QR Code da mesa) aparecem no topo, com som. Toque para marcar como atendido.
- **Tela do pedido**: cardápio com busca e categorias à esquerda; conta aberta e carrinho à direita.
  - Cada mesa tem o **seu carrinho**: dá para começar a mesa 5, atender a mesa 2 e voltar.
  - **Observações rápidas** por item ("Sem cebola", "Bem passado"...), configuráveis em Configurações.
  - Mesas `01` e `1` são a mesma mesa.
- **Pedir a conta**, **servido**, **imprimir conta** e **transferir/juntar mesas** (se a mesa de destino estiver ocupada, os itens são juntados).
- Gerente: **desconto** em R$ ou %, com motivo obrigatório (100% = cortesia), e **cancelar pedido**.
- **Balcão**: ao enviar, escolha **"Enviar para a cozinha"** (cliente paga ao buscar) ou **"Enviar e receber agora"**.
  Pedido pago antes fica na lista do balcão com o selo *Pago* e o botão **Entregar ao cliente**.

## Delivery

- Quadro único: **Aguardando confirmação** (pedidos online: aceitar ou recusar) → **Na cozinha** → **Pronto para sair** → **Na rua**.
- **Saiu para entrega** e **Entregue**. Se o pedido já estava pago, encerra ao entregar; senão, abre o recebimento.
- O pagamento pode ser feito antes (na hora do pedido) ou na entrega.

## Fechar conta

- **Dividir a conta** em 2 a 6 pessoas, com os centavos distribuídos certinho.
- **Várias formas de pagamento** na mesma conta (ex.: metade PIX, metade cartão).
- **Troco** calculado no pagamento em dinheiro.
- **PIX com o valor exato** da conta ou da parte de cada pessoa (QR Code + copia e cola, sem API de banco).
- Quando o valor pago cobre a conta, o pedido é finalizado sozinho. O gerente pode estornar um pagamento.

## Cozinha

- Pedidos com **cronômetro**; ficam destacados após o tempo de atraso configurado.
- **Som** de pedido novo; observações dos itens em destaque.
- **Impressão automática da comanda**, só com os itens novos (acréscimos na mesma mesa não reimprimem o que já saiu). Para imprimir sem a janela de confirmação, abra o Chrome da cozinha com `--kiosk-printing`.
- Lista de pedidos prontos aguardando o garçom.

## Cliente

- **Cartão do cardápio para o suporte de molhos**: QR do Wi-Fi + QR do cardápio, só para consulta (o pedido continua com o garçom). Produtos podem ter descrição.
- **Cardápio digital** pelo QR Code da mesa, com **Chamar garçom** e **Pedir a conta**. QR Codes prontos para imprimir em *Mesas e QR Code*.
- **Pedido online para entrega** (`/pedir/`): o cliente escolhe o bairro (taxa de entrega), envia e pode confirmar pelo WhatsApp. O pedido só vai para a cozinha depois que o gerente aceita. Veja [pedidos-online.md](pedidos-online.md).

## Gestão

- **Caixas**: histórico de cada dia com esperado × contado, sangrias e suprimentos.
- **Configurações em abas** (Loja, Pagamento, Salão e cozinha, Cardápio digital, Delivery): cada aba salva só os seus campos.
- **Relatórios** com **lucro**: custo dos produtos (pela receita ou custo manual, congelado na venda), lucro bruto e margem por produto. Exporta **Excel**, CSV e PDF.
- **Contas a pagar** com vencimentos, alerta de vencidas e saldo do mês (vendas − contas pagas).
- **Bairros e taxas de entrega** (em Configurações → Delivery).
- **Sistema**: versão, backup (automático a cada hora + botão "fazer agora" + download), licença, espaço em disco e últimos erros.
- **Assistente de primeiro uso** para lojas novas (loja, PIX, mesas, categorias).
- **Login com Google** ([login-google.md](login-google.md)).

## Fora do escopo (por enquanto)

| Item | Motivo |
|---|---|
| Taxa de serviço 10% | Pedido do dono: não usar. |
| NFC-e | Exige certificado digital e serviço pago de emissão. |
| Integração iFood | A API do iFood exige parceria/homologação. |
| Confirmação automática do PIX | Exige API do banco; o QR com valor exato resolve sem custo. |
| Painel com vários restaurantes | Precisa de um servidor central na internet. |
