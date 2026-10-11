"""
Script modular para criar atalho da Área de Trabalho com base nas configurações do sistema.
Funciona para qualquer empresa/nome/logo configurado no AppSettings.
Sem dependências externas além de Django e PIL.

Uso:
    python setup_desktop_shortcut.py
"""

import os
import sys
import subprocess
from pathlib import Path

# Adiciona o diretório ao path para imports Django
BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')

import django
django.setup()

from PIL import Image
from restaurante.models import AppSettings


def gerar_icone(logo_path, output_ico):
    """Converte imagem em ícone ICO."""
    try:
        img = Image.open(logo_path)
        img = img.convert('RGB')
        img.thumbnail((256, 256), Image.Resampling.LANCZOS)
        img.save(output_ico, format='ICO')
        return True
    except Exception as e:
        print(f"⚠ Erro ao gerar ícone: {e}")
        return False


def criar_atalho_powershell(shortcut_path, target_script, icon_file, store_name):
    """Usa PowerShell para criar atalho Windows."""
    # Escapar caracteres especiais em nomes
    shortcut_path = str(shortcut_path).replace("'", "''")
    target_script = str(target_script).replace("'", "''")
    icon_file = str(icon_file).replace("'", "''")
    store_name = store_name.replace("'", "''")
    
    ps_command = f"""
$shortcut = '{shortcut_path}'
$target = '{target_script}'
$icon = '{icon_file}'
$description = 'Iniciar {store_name}'

if (-not (Test-Path (Split-Path $shortcut))) {{
    New-Item -ItemType Directory -Path (Split-Path $shortcut) -Force | Out-Null
}}

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($shortcut)
$sc.TargetPath = $target
$sc.WorkingDirectory = Split-Path $target
$sc.Description = $description
if ((Test-Path $icon) -and $icon -ne '') {{ $sc.IconLocation = "$icon,0" }}
$sc.Save()
"""
    
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_command],
            check=False,
            capture_output=True,
            timeout=10,
            text=True
        )
        
        if result.returncode == 0:
            return True
        else:
            print(f"⚠ PowerShell erro: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Erro ao criar atalho: {e}")
        return False


def setup_desktop_shortcut():
    """
    Cria atalho na Área de Trabalho com base nas configurações do sistema.
    Nome e ícone são dinâmicos conforme AppSettings.
    """
    try:
        # 1. Obter configurações do sistema
        settings = AppSettings.get_settings()
        store_name = settings.store_name or "Sistema"
        logo_field = getattr(settings, 'logo', None)
        
        print(f"  Configuração: {store_name}")
        
        # 2. Caminhos
        desktop = Path(os.path.expandvars(r'%USERPROFILE%\Desktop'))
        shortcut_name = f"{store_name}.lnk"
        shortcut_path = desktop / shortcut_name
        
        start_script = BASE_DIR / 'INICIAR_PC_NOVO.bat'
        
        # 3. Diretório de ícones
        icons_dir = BASE_DIR / 'deploy' / 'windows' / 'icons'
        icons_dir.mkdir(parents=True, exist_ok=True)
        
        safe_name = store_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        icon_file = icons_dir / f"{safe_name}.ico"
        
        # 4. Gerar ícone se houver logo
        if logo_field and logo_field.name:
            # Logo pode estar em media/ ou ser caminho relativo
            logo_path = BASE_DIR / logo_field.name
            if not logo_path.exists():
                # Tentar em media/
                logo_path = BASE_DIR / 'media' / logo_field.name
            
            if logo_path.exists():
                if gerar_icone(logo_path, icon_file):
                    print(f"✓ Ícone gerado: {icon_file}")
                else:
                    icon_file = None
            else:
                print(f"⚠ Logo não encontrado: {logo_path}")
                icon_file = None
        else:
            print("⚠ Nenhum logo configurado (deixar em branco em AppSettings > Logo)")
            icon_file = None
        
        # 5. Criar atalho com PowerShell
        if criar_atalho_powershell(shortcut_path, start_script, icon_file or "", store_name):
            print(f"✓ Atalho criado: {shortcut_path}")
            print(f"  Nome: {store_name}")
            return True
        else:
            return False
        
    except Exception as e:
        print(f"✗ Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = setup_desktop_shortcut()
    sys.exit(0 if success else 1)
