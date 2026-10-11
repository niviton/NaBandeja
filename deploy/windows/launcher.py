import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Detecta se está rodando como executável PyInstaller
if getattr(sys, 'frozen', False):
    # Executável - usa o diretório do exe
    BASE_DIR = Path(sys.executable).resolve().parent
    PYTHON_EXE = sys.executable
    IS_FROZEN = True
else:
    # Desenvolvimento - usa venv
    BASE_DIR = Path(__file__).resolve().parents[2]
    PYTHON_EXE = str(BASE_DIR / 'venv' / 'Scripts' / 'python.exe')
    IS_FROZEN = False

WAITRESS_HOST = os.getenv('APP_HOST', '0.0.0.0')
WAITRESS_PORT = int(os.getenv('APP_PORT', '8000'))
DAPHNE_PORT = int(os.getenv('ASGI_PORT', '8001'))
HTTPS_PORT = int(os.getenv('HTTPS_PORT', '443'))

CERT_DIR = BASE_DIR / 'certs'
CERT_FILE = CERT_DIR / 'cert.pem'
KEY_FILE = CERT_DIR / 'key.pem'


def run(command, cwd=BASE_DIR):
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        sock.close()


def start_windows_service(service_name):
    query = run(['sc', 'query', service_name])
    if 'RUNNING' in query.stdout:
        return
    run(['sc', 'start', service_name])


def wait_for_port(host, port, timeout=30):
    started = time.time()
    while time.time() - started < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            try:
                sock.connect((host, port))
                return True
            except Exception:
                time.sleep(0.4)
    return False


def main():
    if not IS_FROZEN and not Path(PYTHON_EXE).exists():
        print('Ambiente virtual não encontrado em venv\\Scripts\\python.exe')
        return 1

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')
    
    # Adiciona o diretório base ao path para imports
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    start_windows_service('postgresql-x64-16')
    start_windows_service('Redis')

    if IS_FROZEN:
        # Modo executável - roda Django com Waitress (WSGI)
        # WebSocket não funciona no .exe, sistema usa HTTP polling como fallback
        import django
        django.setup()
        
        from django.core.management import call_command
        try:
            call_command('migrate', verbosity=0)
            call_command('ensure_initial_access', verbosity=0)
        except Exception as e:
            print(f'Aviso: migrate falhou - {e}')
        
        # Setup desktop shortcut modular (async, non-blocking)
        try:
            subprocess.Popen(
                [PYTHON_EXE, str(BASE_DIR / 'deploy' / 'windows' / 'setup_desktop_shortcut.py')],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass  # Falha silenciosa não impede inicialização
        
        # Inicia servidor Waitress (WSGI)
        import threading
        from waitress import serve
        from nabandeja_project.wsgi import application
        
        def run_server():
            serve(application, host=WAITRESS_HOST, port=WAITRESS_PORT)
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        lan_ip = get_local_ip()
        url = f'http://{lan_ip}:{WAITRESS_PORT}'
        
        if wait_for_port('127.0.0.1', WAITRESS_PORT):
            webbrowser.open(url)
        
        print('Sistema iniciado em:', url)
        print('Pressione Ctrl+C para encerrar')
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        return 0
    else:
        # Modo desenvolvimento - usa subprocessos
        run([PYTHON_EXE, 'manage.py', 'migrate'])
        run([PYTHON_EXE, 'manage.py', 'ensure_initial_access'])
        # Setup desktop shortcut modular (async)
        subprocess.Popen([PYTHON_EXE, 'deploy/windows/setup_desktop_shortcut.py'], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        has_ssl = CERT_FILE.exists() and KEY_FILE.exists()

        if has_ssl:
            # HTTPS mode: single Daphne server handles HTTP + WebSocket over SSL
            ssl_endpoint = (
                f'ssl:{HTTPS_PORT}'
                f':certKey={CERT_FILE}'
                f':privateKey={KEY_FILE}'
                f':interface=0.0.0.0'
            )
            daphne_cmd = [
                PYTHON_EXE, '-m', 'daphne',
                '-e', ssl_endpoint,
                'nabandeja_project.asgi:application',
            ]
            main_proc = subprocess.Popen(daphne_cmd, cwd=BASE_DIR)

            lan_ip = get_local_ip()
            url = f'https://{lan_ip}' if HTTPS_PORT == 443 else f'https://{lan_ip}:{HTTPS_PORT}'

            if wait_for_port('127.0.0.1', HTTPS_PORT):
                webbrowser.open(url)

            print(f'Sistema iniciado em: {url}  [HTTPS]')
            print('Pressione Ctrl+C para encerrar')

            try:
                while True:
                    time.sleep(1)
                    if main_proc.poll() is not None:
                        break
            except KeyboardInterrupt:
                pass
            finally:
                if main_proc.poll() is None:
                    main_proc.terminate()
        else:
            # HTTP mode (fallback) - Waitress + Daphne
            waitress_cmd = [
                PYTHON_EXE, '-m', 'waitress',
                f'--listen={WAITRESS_HOST}:{WAITRESS_PORT}',
                'nabandeja_project.wsgi:application',
            ]
            daphne_cmd = [
                PYTHON_EXE, '-m', 'daphne',
                '-b', WAITRESS_HOST,
                '-p', str(DAPHNE_PORT),
                'nabandeja_project.asgi:application',
            ]

            waitress_proc = subprocess.Popen(waitress_cmd, cwd=BASE_DIR)
            daphne_proc = subprocess.Popen(daphne_cmd, cwd=BASE_DIR)

            lan_ip = get_local_ip()
            url = f'http://{lan_ip}:{WAITRESS_PORT}'

            if wait_for_port('127.0.0.1', WAITRESS_PORT):
                webbrowser.open(url)

            print(f'Sistema iniciado em: {url}')
            print('Para ativar HTTPS: execute deploy/windows/setup_ssl.bat como Administrador')
            print('Pressione Ctrl+C para encerrar')

            try:
                while True:
                    time.sleep(1)
                    if waitress_proc.poll() is not None or daphne_proc.poll() is not None:
                        break
            except KeyboardInterrupt:
                pass
            finally:
                for process in [waitress_proc, daphne_proc]:
                    if process.poll() is None:
                        process.terminate()

        return 0


if __name__ == '__main__':
    sys.exit(main())
