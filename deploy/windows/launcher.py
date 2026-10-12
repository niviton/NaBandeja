"""
Inicia o NaBandeja no PC do estabelecimento.

Usado tanto pelo código-fonte (start_system.bat, com o Python do venv) quanto
pelo executável NaBandeja.exe (PyInstaller).

1. cria o .env no primeiro início (chave secreta + senha do gerente);
2. aplica as migrações e garante um gerente;
3. atualiza o atalho da Área de Trabalho;
4. sobe o Daphne, que atende páginas e WebSocket (tempo real) na mesma porta,
   e também HTTPS se houver certificado em certs/;
5. abre o navegador.
"""

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

IS_FROZEN = getattr(sys, 'frozen', False)
if IS_FROZEN:
    DATA_DIR = Path(sys.executable).resolve().parent
    CODE_DIR = DATA_DIR / '_internal'
else:
    DATA_DIR = CODE_DIR = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(CODE_DIR))
os.chdir(DATA_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')

from nabandeja_project.envfile import ensure_env_file  # noqa: E402

CERT_DIR = DATA_DIR / 'certs'
CERT_FILE = CERT_DIR / 'cert.pem'
KEY_FILE = CERT_DIR / 'key.pem'


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def wait_and_open_browser(port, url, timeout=60):
    started = time.time()
    while time.time() - started < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                webbrowser.open(url)
                return
        time.sleep(0.5)


def update_desktop_shortcut():
    try:
        sys.path.insert(0, str(CODE_DIR / 'deploy' / 'windows'))
        import setup_desktop_shortcut
        setup_desktop_shortcut.setup_desktop_shortcut()
    except Exception as exc:  # o atalho é conveniência; nunca impede o sistema de subir
        print(f'Aviso: não foi possível atualizar o atalho ({exc}).')


def backup_loop(interval_minutes):
    """Backup automático do banco enquanto o sistema estiver aberto."""
    from restaurante.services.backup import run_backup
    while True:
        try:
            run_backup()
        except Exception as exc:
            print(f'Aviso: backup automático falhou ({exc}).')
        time.sleep(interval_minutes * 60)


def main():
    sys.stdout.reconfigure(line_buffering=True)
    initial_password = ensure_env_file(DATA_DIR)

    from dotenv import load_dotenv
    load_dotenv(DATA_DIR / '.env')

    import django
    django.setup()
    from django.core.management import call_command

    print('Preparando banco de dados...')
    call_command('migrate', interactive=False, verbosity=0)
    call_command('ensure_initial_access')
    if os.getenv('NABANDEJA_SUPPORT_HASH', '').strip():
        call_command('suporte_nabandeja')  # usa o hash do .env
    interval = int(os.getenv('BACKUP_INTERVAL_MINUTES', '60'))
    if interval > 0:
        threading.Thread(target=backup_loop, args=(interval,), daemon=True).start()
    if os.getenv('NABANDEJA_SKIP_SHORTCUT', '').lower() not in ('1', 'true'):
        threading.Thread(target=update_desktop_shortcut, daemon=True).start()

    http_port = int(os.getenv('APP_PORT', '8000'))
    https_port = int(os.getenv('HTTPS_PORT', '443'))
    host = os.getenv('APP_HOST', '0.0.0.0')
    lan_ip = get_local_ip()

    endpoints = [f'tcp:port={http_port}:interface={host}']
    url = f'http://{lan_ip}:{http_port}'
    if CERT_FILE.exists() and KEY_FILE.exists():
        cert, key = (str(path).replace('\\', '/').replace(':', '\\:') for path in (CERT_FILE, KEY_FILE))
        endpoints.append(f'ssl:port={https_port}:interface={host}:certKey={cert}:privateKey={key}')
        url = f'https://{lan_ip}' + ('' if https_port == 443 else f':{https_port}')

    print('=' * 60)
    print(f'  NaBandeja rodando em: {url}')
    print(f'  Celulares e tablets: use esse endereço na mesma rede Wi-Fi.')
    if initial_password:
        print(f'  Primeiro acesso -> usuário: gerente  senha: {initial_password}')
    print('  Para encerrar, feche esta janela.')
    print('=' * 60)

    if os.getenv('NABANDEJA_NO_BROWSER', '').lower() not in ('1', 'true'):
        threading.Thread(target=wait_and_open_browser, args=(http_port, url), daemon=True).start()

    from daphne.cli import CommandLineInterface

    args = []
    for endpoint in endpoints:
        args += ['-e', endpoint]
    args += ['-v', '0', 'nabandeja_project.asgi:application']
    CommandLineInterface().run(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
