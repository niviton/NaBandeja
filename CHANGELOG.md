# Changelog

Mudanças relevantes do NaBandeja. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [3.2.0] - 2026-10-12

### Painel master
- Novo modo **`NABANDEJA_MODO=master`** (`INICIAR_MASTER.bat`): o dono do NaBandeja vê todas as empresas,
  cria empresas novas (ou importa o banco de uma loja), **entra** em qualquer uma e gera o **instalador** de cada loja.
- Cada empresa ganha um **repositório privado de dados** (`nabandeja-dados-<código>`) e uma **chave de envio**
  que só escreve nele (deploy key). O código do sistema nunca mais recebe dados de clientes.
- **Backup externo criptografado** (X25519 + AES-256-GCM): só a chave mestra do painel abre. A loja envia a
  cada hora e pelo botão **Salvar dados** no rodapé; um ponto de restauração por dia (14 dias).
- "Entrar na empresa" abre a empresa num processo próprio: editável em implantação, **somente leitura** depois
  que a loja está em produção.

### Tempo real modular
- O mesmo código roda no PC Windows (ASGI), no **Termux**, no **Railway/VPS** e no **PythonAnywhere** (só WSGI).
- Os eventos ficam num registro no banco: o WebSocket entrega na hora e o **polling** (`/tempo-real/eventos/`)
  entrega os mesmos eventos em qualquer servidor. Sons e avisos agora funcionam também sem WebSocket.
- `python -m nabandeja_project.servir`: escolhe Daphne (ASGI) ou WSGI conforme o que estiver instalado.
- `REDIS_URL` para vários processos, `DATABASE_URL` e domínio do Railway reconhecidos.
- Dependências separadas por ambiente em `requirements/`.

### Alterado
- Nova logo (símbolo, logo horizontal, favicons e ícones do app).

### Removido
- `novo_cliente.py`, `NOVO_CLIENTE.bat` e o backup que fazia commit do banco **sem criptografia** no repositório
  do código (`auto_backup_git_push.ps1`). Veja docs/clientes.md para migrar clientes do modelo antigo.

## [3.1.0] - 2026-10-11

### Fluxo reorganizado
- Navegação única para todos: **Hoje · Salão · Delivery · Cozinha · Gestão** (cada função vê só as suas áreas).
  A Gestão agrupa o resto em Vendas, Cardápio, Loja e Sistema.
- **Hoje** substitui o antigo Painel: **abrir o dia** (caixa + loja juntos), **fechar o dia** com checklist do
  que ficou aberto e contagem da gaveta, **pausar pedidos**.
- Caixa: **sangria e suprimento**, **histórico de caixas** e resumo do fechamento para imprimir.
- **Reabrir conta** fechada por engano (gerente, com motivo, só com o caixa do dia aberto).
- **Quadro de Delivery**: pedidos online, cozinha, pronto para sair, na rua; botões *Saiu* e *Entregue*.
- **Balcão**: pagar antes ("Enviar e receber agora") ou ao buscar; *Entregar ao cliente* para pedidos já pagos.
- **Configurações em abas**; cada aba salva só os seus campos (um checkbox de outra aba não é mais desmarcado).
- Barra de navegação compacta no celular (ícone + rótulo).

## [3.0.0] - 2026-10-11

### Novo visual
- Identidade **NaBandeja** (marca com cloche e bandeja) e design system documentado em `DESIGN.md`:
  fundo creme, destaque tomate, títulos em Fraunces, rótulos em mono, componentes `nb-*`.
- Todas as telas refeitas (salão, pedido, conta, cozinha, painel, relatórios, cardápio, configurações,
  páginas do cliente) com foco em toque no celular e leitura rápida.
- Acessibilidade: rótulos em todos os campos, foco visível, nomes acessíveis, `prefers-reduced-motion`,
  confirmação com `<dialog>` nativo, texto mínimo de 12 px, sem rolagem lateral no celular.

### Adicionado
- Login com **empresa + usuário + senha**; tela inicial só com a marca NaBandeja.
- **Superusuário de suporte** (`suporte_nabandeja`) com página própria: código da empresa,
  **módulos ligados por cliente**, licença e redefinição de senhas.
- Painel e delivery atualizam em tempo real.

### Alterado
- Gerentes das lojas deixam de ser superusuários do Django (só o suporte acessa `/admin/`).
- Lucro bruto só aparece quando há custo cadastrado.

## [2.3.0] - 2026-10-11

### Adicionado
- **Cartão do cardápio** para o suporte de molhos: QR para conectar ao Wi-Fi + QR do cardápio (só consulta), pronto para imprimir.
- Descrição dos produtos e busca no cardápio digital.
- `PUBLIC_BASE_URL` para os QR Codes apontarem para um endereço na internet.

### Corrigido
- QR Codes gerados pelo próprio computador do sistema apontavam para `localhost`; agora usam o IP da rede.

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
