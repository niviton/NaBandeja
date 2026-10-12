"""
Sobe o NaBandeja em qualquer ambiente com o melhor servidor disponível.

    python -m nabandeja_project.servir [--migrate] [--host 0.0.0.0] [--port 8000] [--wsgi]

- Daphne + Channels instalados: ASGI, páginas e WebSocket na mesma porta;
- sem eles (ou com --wsgi): servidor WSGI com threads do próprio Django e o
  tempo real em polling. Serve para o Termux quando o twisted não instala.

Lê PORT (Railway, Render) ou APP_PORT e APP_HOST. No PC Windows da loja,
continue usando deploy\\windows\\start_system.bat (tem HTTPS, atalho e backup).
No PythonAnywhere não use este arquivo: aponte o WSGI para nabandeja_project.wsgi.
"""

import argparse
import importlib.util
import os
import sys


def has_asgi_server():
    return all(importlib.util.find_spec(name) is not None for name in ('daphne', 'channels'))


def choose_server(force_wsgi=False):
    return 'wsgi' if force_wsgi or not has_asgi_server() else 'asgi'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Sobe o NaBandeja (ASGI com WebSocket ou WSGI com polling).')
    parser.add_argument('--host', default=os.getenv('APP_HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT') or os.getenv('APP_PORT') or 8000))
    parser.add_argument('--migrate', action='store_true', help='Aplica as migrações antes de subir.')
    parser.add_argument('--wsgi', action='store_true', help='Força WSGI (sem WebSocket).')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    server = choose_server(args.wsgi)
    # Antes de carregar as configurações: decide o transporte do tempo real.
    os.environ['NABANDEJA_SERVIDOR'] = server
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')

    import django
    django.setup()
    from django.core.management import call_command

    if args.migrate:
        call_command('migrate', interactive=False, verbosity=1)

    realtime = 'WebSocket (polling de reserva)' if server == 'asgi' else 'polling HTTP'
    print(f'NaBandeja em http://{args.host}:{args.port}  ·  servidor {server.upper()}  ·  tempo real: {realtime}', flush=True)

    if server == 'asgi':
        from daphne.cli import CommandLineInterface
        CommandLineInterface().run([
            '-b', args.host, '-p', str(args.port), '--proxy-headers', '-v', '1', 'nabandeja_project.asgi:application',
        ])
    else:
        from django.core.servers.basehttp import run
        from django.core.wsgi import get_wsgi_application
        run(args.host, args.port, get_wsgi_application(), threading=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
