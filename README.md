<h1 align="center">🍽️ NaBandeja</h1>

<p align="center">
  Sistema de gestão para restaurantes, lanchonetes, bares e pizzarias.<br>
  Pedidos por mesa, cozinha em tempo real, estoque, caixa e relatórios, rodando na rede local do estabelecimento.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-4.2%2B-092E20?logo=django&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-execut%C3%A1vel-0078D6?logo=windows&logoColor=white">
  <img alt="PWA" src="https://img.shields.io/badge/PWA-instal%C3%A1vel-5A0FC8">
</p>

---

## Funcionalidades

| Módulo | O que faz |
|---|---|
| **Garçom** (`/garcom/`) | Abre mesas e pedidos de delivery pelo celular. |
| **Cozinha** (`/cozinha/`) | Recebe os pedidos na hora e marca quando ficam prontos. |
| **Painel do gerente** (`/admin-panel/`) | Dashboard, caixa, cardápio, equipe, relatórios e configurações. |
| **Estoque** | Controle por produto ou por ingrediente, com alerta de estoque baixo. |
| **Caixa** | Abertura e fechamento, com resumo de pagamentos. |
| **Relatórios** | Vendas por período, por garçom e produtos mais vendidos. |
| **Cupom** | Impressão térmica com QR Code PIX. |
| **Personalização** | Nome, logo, cores e fonte de cada loja, sem mexer no código. |
| **Tempo real** | Atualização via WebSocket, com polling como alternativa. |
| **PWA** | Instalável na tela inicial do celular. |

## Início rápido

Requisitos: **Windows** e **Python 3.11+**.

```powershell
git clone https://github.com/niviton/nabandeja.git
cd nabandeja
.\INICIAR_PC_NOVO.bat
```

O script cria o ambiente virtual, instala as dependências, aplica as migrações, cria o usuário `gerente` e abre o navegador. A senha aparece no terminal. Para escolher a senha, defina `NABANDEJA_INIT_ADMIN_PASSWORD` no `.env`.

Para outras formas de instalar (manual, executável `.exe` ou Linux/Mac), veja [docs/instalacao.md](docs/instalacao.md).

## Um sistema, vários clientes

O NaBandeja é **modular**: o mesmo código atende vários estabelecimentos, e cada cliente tem sua própria branch.

```
main                      ← produto: toda melhoria é feita aqui
├── cliente/billa-burguer ← código da main + banco, logo e fotos do cliente
└── cliente/<novo>        ← criado com NOVO_CLIENTE.bat
```

```powershell
python scripts/novo_cliente.py "Pizzaria do João"   # cria o cliente
git switch cliente/pizzaria-do-joao; git merge main   # leva melhorias ao cliente
```

O passo a passo completo está em [docs/clientes.md](docs/clientes.md).

## Documentação

| Guia | Conteúdo |
|---|---|
| [Instalação](docs/instalacao.md) | Rodar pelo código-fonte, primeiro acesso, problemas comuns |
| [Clientes](docs/clientes.md) | Criar, atualizar e fazer backup de clientes |
| [Implantação no Windows](docs/deploy-windows.md) | Executável `.exe`, rede local, firewall, HTTPS, atalho na Área de Trabalho |
| [Backup](docs/backup.md) | Backups automáticos de SQLite e PostgreSQL |
| [Tempo real](docs/tempo-real.md) | WebSocket, eventos e PWA |
| [Segurança](docs/seguranca.md) | Variáveis de ambiente e checklist de produção |
| [Melhorias](docs/melhorias.md) | Checklist do que melhorar (roadmap) |

## Estrutura do projeto

```
.
├── nabandeja_project/     # Configuração Django (settings, urls, asgi/wsgi)
├── restaurante/           # App principal: models, views, forms, realtime
│   ├── management/        # Comandos: ensure_initial_access, security_audit, ...
│   └── migrations/
├── templates/             # Páginas HTML (garçom, cozinha, painel, PWA)
├── static/                # Arquivos estáticos e ícones do PWA
├── media/                 # Uploads do cliente (logo, fotos de produtos)
├── deploy/windows/        # Launcher, build do .exe, backup, HTTPS, atalho
├── scripts/               # novo_cliente.py, initial_data.py
├── tests/                 # Teste end-to-end com Selenium
├── docs/                  # Documentação
├── INICIAR_PC_NOVO.bat    # Instala e inicia o sistema
├── NOVO_CLIENTE.bat       # Cria um novo cliente
├── NaBandeja.spec         # Build do executável (PyInstaller)
└── manage.py
```

## Tecnologias

Django · Django Channels · Daphne · Waitress · SQLite/PostgreSQL · Bootstrap 5 · PyInstaller

## Licença

Software proprietário. Todos os direitos reservados. Veja [LICENSE](LICENSE).
