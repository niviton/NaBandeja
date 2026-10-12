# DESIGN.md — NaBandeja

Design system do NaBandeja. Toda tela nova segue este arquivo. Implementação: `frontend/tailwind.config.js` (tokens) e `frontend/app.css` (componentes `nb-*`).

## 1. Tema visual e atmosfera

**"Servido na bandeja."** Hospitalidade de restaurante brasileiro com acabamento de produto sério: papel de comanda, louça branca, molho de tomate. Quente, calmo, legível no corre-corre do salão.

- Fundo creme (papel), superfícies brancas (louça), tinta carvão.
- Um único destaque forte: **Tomate**. Usado em ação principal, foco e na palavra de ênfase dos títulos.
- Títulos em serifa editorial (Fraunces) com **uma palavra em itálico tomate**. Rótulos pequenos em mono, caixa alta, espaçados (como etiqueta de comanda).
- Operação primeiro: números grandes, toque fácil, nada decorativo atrapalhando.

## 2. Paleta de cores e papéis

| Token | Hex | Papel |
|---|---|---|
| `creme` | `#FAF6EF` | Fundo das telas |
| `papel` | `#FFFFFF` | Superfícies (cards, campos) |
| `linha` | `#E9E1D4` | Bordas e divisórias |
| `carvao` | `#1F1A17` | Texto principal, botão escuro |
| `fumaca` | `#6E655C` | Texto secundário |
| `tomate` | `#D9442B` | Marca, ação principal, foco, ênfase |
| `brasa` | `#B23620` | Hover/pressionado do tomate |
| `mostarda` | `#E9A23B` | Na cozinha / atenção |
| `manjericao` | `#2E7D57` | Pronto / sucesso / pago |
| `uva` | `#6D3B8C` | Conta pedida |
| `cebola` | `#2563A8` | Ocupada (servida) / informação |
| `pimenta` | `#C0262D` | Erro / cancelar / atrasado |

Fundos suaves de status: `-50` de cada cor (ex.: `mostarda-50 #FDF3E1`). Status **sempre** com texto, nunca só cor.

Cozinha usa o tema escuro: fundo `carvao`, cartões `papel`.

## 3. Tipografia

| Uso | Fonte | Peso/tamanho |
|---|---|---|
| Títulos de página e números de destaque | Fraunces (serif, variável) | 600, 28–40 px; ênfase em itálico tomate |
| Interface e texto | Inter (variável) | 400–700, base 15–16 px |
| Rótulos (kicker), códigos, totais tabulares | JetBrains Mono | 500, 11–12 px, caixa alta, `tracking 0.14em` |

Mínimo de 13 px em qualquer texto lido. Valores em dinheiro com `tabular-nums`.

## 4. Componentes

- **Botões** (`nb-btn`): altura mínima 44 px (toque). `nb-btn-primary` (tomate), `nb-btn-dark` (carvão), `nb-btn-secondary` (papel + linha), `nb-btn-ghost`, `nb-btn-danger`. Um primário por área.
- **Campos** (`nb-input`, `nb-select`, `nb-textarea`): papel, borda linha, raio 12 px, foco com anel tomate. Sempre com `<label>` visível e `autocomplete` correto.
- **Cards** (`nb-card`): papel, borda linha, raio 20 px, sombra mínima. **Nunca card dentro de card**: dentro de um card, separe com divisórias.
- **Kicker** (`nb-kicker`): rótulo mono acima do título.
- **Chips** (`nb-chip`): filtros e observações rápidas.
- **Status** (`nb-status-*`): pílula com cor suave + texto.
- **Mesa** (`nb-table`): quadrado com número grande em Fraunces e status embaixo.

## 5. Layout

- Escala de espaço de 4 px: 4, 8, 12, 16, 24, 32, 48.
- Conteúdo em até 1280 px; formulários em até 640 px.
- Páginas: kicker + título + linha de apoio, depois o conteúdo. Ações da página à direita do título (abaixo no celular).
- Grade de mesas: 3 colunas no celular, até 8 no desktop.

## 6. Profundidade

Plano por padrão. Sombra só para o que flutua (menu do celular, avisos): `0 12px 32px -16px rgb(31 26 23 / 0.25)`. Cards usam borda, não sombra.

## 7. Pode e não pode

**Pode:** muito respiro, um destaque por tela, números grandes, linguagem direta ("Fechar conta", não "Finalizar transação").

**Não pode:**
- hero escuro centralizado e gradientes chamativos (cara de template de IA);
- card dentro de card;
- excesso de selos e etiquetas;
- texto menor que 13 px;
- ícone sem texto em ação importante (ícone sozinho só com `aria-label`);
- animação que não respeita `prefers-reduced-motion`.

## 8. Responsivo

- Pensado primeiro para o celular do garçom (390 px).
- Área de toque mínima 44 × 44 px; `touch-action: manipulation` em botões.
- Menu do painel vira barra rolável no topo abaixo de 1024 px.
- Tabelas largas ficam dentro de contêiner com rolagem horizontal.

## 9. Guia para o agente

- Cor de bolso: fundo `#FAF6EF`, texto `#1F1A17`, ação `#D9442B`.
- Título: `<p class="nb-kicker">Salão</p><h1 class="nb-title">Mesas do <em>salão</em></h1>`.
- Antes de entregar: rodar `python manage.py test restaurante`, recompilar o CSS (`scripts\build_css.bat`) e conferir prints no celular e no desktop.
