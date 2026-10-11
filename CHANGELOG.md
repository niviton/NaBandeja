# Changelog

Mudanças relevantes do NaBandeja. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [2.2.0] - 2026-10-11

### Adicionado
- **Salão com mapa de mesas** (cores por situação), carrinho por mesa, observações rápidas por item, pedir a conta, servido, transferir/juntar mesas.
- **Fechar conta**: dividir por pessoas, várias formas de pagamento, troco, PIX do valor de cada parte, estorno (gerente).
- **Desconto e cortesia** com motivo (gerente).
- **Cozinha**: cronômetro e atraso configurável, som, impressão automática da comanda só com itens novos.
- **Cardápio digital pelo QR Code da mesa** (chamar garçom, pedir a conta) e folha de QR Codes para imprimir.
- **Pedido online** com bairros/taxa de entrega, pedido mínimo, confirmação pelo gerente e link do WhatsApp.
- **Lucro** nos relatórios (custo congelado na venda) e exportação para **Excel**.
- **Contas a pagar** e saldo do mês; **caixa** com tela própria no Painel.
- **Sistema**: status, backup automático a cada hora (e manual/download), licença por cliente assinada (Ed25519).
- **Assistente de primeiro uso** e menu do painel responsivo.
- `SQLITE_PATH` para usar o banco em outro local.

### Alterado
- Caixa e relatórios passam a somar **pagamentos** (contas divididas contam certo).
- Telas da equipe refeitas com htmx (fragmentos HTML do servidor) e `static/js/nabandeja.js`.
- Avisos na tela não interpretam HTML (fecha brecha de injeção).

## [2.1.0] - 2026-10-11

### Adicionado
- **Login com Google** para a equipe (só entra quem o gerente cadastrou com aquele e-mail).
- Edição de membros da equipe (nome, e-mail, função, nova senha).
- PIX com valor exato no cupom e na tela de fechar conta (BR Code oficial, gerado offline, sem API de banco).
- Bloqueio de login após 5 senhas erradas; logs de erro em `logs/nabandeja.log`.
- `.env` criado automaticamente no primeiro início (chave secreta e senha do gerente próprias).
- `ATUALIZAR.bat`: atualização em 1 clique com backup antes.
- Testes automatizados (51) e CI no GitHub Actions.

### Corrigido
- Excluir produto/categoria apagava o histórico de vendas: agora são desativados e o banco protege o histórico.
- Estoque podia ficar errado com dois pedidos simultâneos (baixa atômica no banco).
- Caixa somava PIX e cartão como dinheiro na gaveta.
- Tempo real nunca conectava (WebSocket em outra porta) e notificações vinham duplicadas.
- Era possível fechar conta de pedido cancelado; total usava preço antigo guardado no carrinho.
- `DEBUG` ligado por padrão em produção.

### Alterado
- Código reorganizado: `views/` por área, regras de negócio em `services/`, permissões em `permissions.py`.
- Um único servidor (Daphne) para páginas e tempo real; WhiteNoise para arquivos estáticos.
- Dependências com versões fixas; `requirements-dev.txt` separado.
- Garçom pode atender qualquer mesa do salão (antes só os pedidos que ele abriu).
- Usuários removidos passam a ser desativados (o histórico mantém o nome).

## [2.0.0] - 2026-10-11

Projeto renomeado de **Billar / Sistema Restaurante** para **NaBandeja**, com estrutura para atender vários clientes.

### Adicionado
- Modelo de **uma branch por cliente** (`cliente/<slug>`).
- `scripts/novo_cliente.py` e `NOVO_CLIENTE.bat` para criar um cliente com banco limpo.
- Manifest do PWA com nome e cores da loja de cada cliente.
- Documentação organizada em `docs/`.
- `LICENSE`, `.gitattributes` e `.editorconfig`.

### Alterado
- Projeto movido para a raiz do repositório; pacote `billar_project` → `nabandeja_project`.
- Executável `SistemaRestaurante.exe` → `NaBandeja.exe`, e o `.spec` deixou de depender de um caminho fixo do PC.
- Nome padrão da loja passou a ser "Meu Restaurante" (migração `0012`).
- Variáveis `BILLAR_INIT_ADMIN_*` → `NABANDEJA_INIT_ADMIN_*` (as antigas continuam aceitas).
- Pastas de backup e tarefas agendadas renomeadas para `NaBandeja`.

### Removido
- Artefato de teste do Selenium que estava versionado.

## [1.x] - até 2026-03

Versões como **Billá Burger / Billar**: pedidos por mesa e delivery, cozinha em tempo real (WebSocket com polling como alternativa), estoque por ingrediente, caixa, relatórios, cupom térmico com PIX, executável Windows, HTTPS na rede local e atalho dinâmico na Área de Trabalho.
