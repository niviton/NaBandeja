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
| **Salão** | Mapa de mesas com cores por situação, chamados do cliente, carrinho por mesa, observações rápidas, transferir/juntar mesas. |
| **Conta** | Dividir por pessoas, várias formas de pagamento, troco, desconto/cortesia, **PIX com valor exato** (sem API de banco). |
| **Cozinha** | Tempo real, cronômetro e atraso, som de pedido novo, impressão automática da comanda (só itens novos). |
| **Cliente** | Cardápio digital pelo **QR Code da mesa** (chamar garçom, pedir a conta) e **pedido online** com taxa por bairro. |
| **Gestão** | Caixa por turno, relatórios com **lucro por produto**, Excel/CSV/PDF, contas a pagar, estoque por ingrediente. |
| **Sistema** | Funciona **sem internet**, backup automático, **login com Google**, licença por cliente, assistente de primeiro uso, PWA. |

Lista completa em [docs/funcionalidades.md](docs/funcionalidades.md).

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
| [Login com Google](docs/login-google.md) | Entrar com a conta Google, sem depender de senha |
| [Segurança](docs/seguranca.md) | Variáveis de ambiente e checklist de produção |
| [Funcionalidades](docs/funcionalidades.md) | Tudo o que o sistema faz |
| [Pedidos online](docs/pedidos-online.md) | Cardápio digital, delivery pelo site e acesso pela internet |
| [Licenças](docs/licenca.md) | Emitir e instalar licenças por cliente |
| [Desenvolvimento](docs/desenvolvimento.md) | Organização do código, CSS e testes |
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

Django · Django Channels · Daphne · WhiteNoise · SQLite/PostgreSQL · Tailwind CSS · PyInstaller

## Licença

Software proprietário. Todos os direitos reservados. Veja [LICENSE](LICENSE).
