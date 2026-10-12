"""
Sobe UMA empresa aberta pelo painel master, num processo só dela.

Cada empresa tem banco, fotos, cache e tempo real próprios: nada se mistura
com o painel nem com outras empresas. O painel passa tudo por variáveis de
ambiente (restaurante/services/espelho.py) e fala com este processo pela
entrada padrão: quando o painel fecha, a entrada termina e a empresa fecha junto.

    python -m nabandeja_project.espelho <porta>
"""

import os
import sys
import threading


def _close_with_parent():
    try:
        sys.stdin.read()
    finally:
        os._exit(0)


def main():
    port = int(sys.argv[1])
    threading.Thread(target=_close_with_parent, daemon=True).start()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')

    import django
    django.setup()
    from django.core.management import call_command

    # Backups antigos podem vir de uma versão anterior do sistema.
    call_command('migrate', interactive=False, verbosity=0)

    from daphne.cli import CommandLineInterface
    CommandLineInterface().run(['-b', '127.0.0.1', '-p', str(port), '-v', '0', 'nabandeja_project.asgi:application'])


if __name__ == '__main__':
    main()
