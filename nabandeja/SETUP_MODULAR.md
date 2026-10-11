# Setup Modular do Sistema - Guia de Uso

## O que foi implementado

Um sistema **100% modular** que cria atalhos na Área de Trabalho com base nas **configurações do sistema**:
- **Nome do atalho**: Vem do `AppSettings.store_name`
- **Ícone do atalho**: Vem do `AppSettings.logo`
- **Descrição**: Dinâmica conforme nome da loja

## Como Funciona

### 1. **Criação Automática (Primeira Vez)**
Ao rodar `INICIAR_PC_NOVO.bat`, o sistema:
- Cria ambiente virtual
- Aplica migrações
- Cria usuário padrão (`gerente / admin123`)
- **Ejecuta automaticamente** o setup_desktop_shortcut.py
- Abre o navegador com o sistema

### 2. **Atualizar Atalho (Segundo Plano)**
O script **se executa sempre em background** durante a inicialização, sem travar nada:
- Se mudar as configurações (nome ou logo da loja), o atalho é atualizado
- O ícone é regenerado em `deploy/windows/icons/`

### 3. **Alterar Nome e Logo**

1. **Acesse o sistema** em `http://localhost:8000`
2. **Login**: `gerente` / `admin123`
3. **Menu** > **Configurações**
4. Altere:
   - **Nome da Loja**: Ex. "Pizzaria Gourmet"
   - **Logo**: Envie uma imagem (PNG, JPG)
5. **Salve**
6. **Próxima vez que iniciar**, o atalho será atualizado com o novo nome e logo

## Exemplos de Uso

### Exemplo 1: Pizzaria
```
Nome da Loja: Pizzaria Gourmet
Logo: [imagem pizza.png]
Resultado: Atalho "Pizzaria Gourmet.lnk" com logo da pizza
```

### Exemplo 2: Bar & Restaurante
```
Nome da Loja: Bar do João
Logo: [imagem bar.jpg]
Resultado: Atalho "Bar do João.lnk" com logo do bar
```

## Executar Manualmente (Opcional)

Se precisar forçar atualização do atalho:

```bash
python manage.py setup_desktop_shortcut
```

Ou rodar o script direto:

```bash
python deploy/windows/setup_desktop_shortcut.py
```

## Arquivos Criados

- `deploy/windows/setup_desktop_shortcut.py` - Script principal de setup
- `restaurante/management/commands/setup_desktop_shortcut.py` - Comando Django
- `deploy/windows/icons/` - Pasta com ícones gerados
- `INICIAR_PC_NOVO.bat` - Simplificado, apenas chama start_system.bat

## Fluxo Completo

```
INICIAR_PC_NOVO.bat (duplo clique no Desktop)
    ↓
start_system.bat (setup inicial)
    ├─ venv (criar se não existir)
    ├─ pip install (dependências)
    ├─ migrate (banco de dados)
    ├─ ensure_initial_access (usuário gerente/admin123)
    ├─ setup_desktop_shortcut.py (criar atalho dinâmico) ← NOVO!
    └─ launcher.py (iniciar Django + abrir navegador)
```

## Vantagens da Solução Modular

✅ **Reutilizável**: Funciona para qualquer empresa/nome  
✅ **Dinâmico**: Atalho e ícone mudam conforme AppSettings  
✅ **Automático**: Sem ação do usuário após setup inicial  
✅ **Sem Dependências**: Usa apenas PIL (já instalado) e PowerShell  
✅ **Robustez**: Tratamento de caracteres especiais (acentos, etc)  
✅ **CLI opcional**: Pode ser chamado manualmente se necessário  

---

**Data**: Março 2026  
**Status**: ✅ Implementado e testado
