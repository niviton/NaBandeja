import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import subprocess
from pathlib import Path


class Command(BaseCommand):
    help = 'Cria/atualiza atalho na Área de Trabalho com nome e logo do sistema.'

    def handle(self, *args, **options):
        """Executa script de setup do atalho desktop."""
        base_dir = Path(__file__).resolve().parents[3]
        setup_script = base_dir / 'deploy' / 'windows' / 'setup_desktop_shortcut.py'
        
        try:
            result = subprocess.run(
                [f"{base_dir}/venv/Scripts/python.exe", str(setup_script)],
                cwd=base_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                self.stdout.write(result.stdout)
            if result.stderr:
                self.stderr.write(result.stderr)
            
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('✓ Atalho atualizado com sucesso'))
            else:
                self.stdout.write(self.style.ERROR('✗ Erro ao criar atalho'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro: {e}'))
