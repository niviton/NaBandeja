# Changelog

Mudanças relevantes do NaBandeja. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

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
