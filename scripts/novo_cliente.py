"""
NaBandeja - cria um novo cliente.

Cada cliente vive na sua própria branch (cliente/<slug>), criada a partir da
main. A branch nasce com banco limpo, sem fotos/ícones de outros clientes, e
com o nome da loja já configurado.

Uso:
    python scripts/novo_cliente.py "Pizzaria do João"
    python scripts/novo_cliente.py "Pizzaria do João" --slogan "A melhor pizza do bairro" --cor "#16a34a"

Depois, para levar melhorias da main para um cliente:
    git switch cliente/<slug>
    git merge main
"""

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]

# Arquivos de um cliente que não devem ir para outro cliente
CLIENT_MEDIA_DIRS = ['media/products', 'media/settings']
CLIENT_ICONS_DIR = 'deploy/windows/icons'


def slugify(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def run(cmd, **kwargs):
    print('  $', ' '.join(str(c) for c in cmd))
    return subprocess.run(cmd, cwd=PROJECT_DIR, check=True, **kwargs)


def git_output(*args):
    return subprocess.run(
        ['git', *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


def find_python():
    venv_python = PROJECT_DIR / 'venv' / 'Scripts' / 'python.exe'
    return str(venv_python) if venv_python.exists() else sys.executable


def tracked_files_in(folder):
    # -z evita que o git escape nomes com acento (ex: "Bill\303\241.ico")
    out = subprocess.run(
        ['git', 'ls-files', '-z', '--', folder], cwd=PROJECT_DIR, check=True, capture_output=True
    ).stdout.decode('utf-8')
    return [name for name in out.split('\0') if name and not name.endswith('.gitkeep')]


def main():
    parser = argparse.ArgumentParser(description='Cria um novo cliente NaBandeja em uma branch própria.')
    parser.add_argument('nome', help='Nome da loja, ex: "Pizzaria do João"')
    parser.add_argument('--slug', help='Identificador da branch (padrão: gerado a partir do nome)')
    parser.add_argument('--slogan', default='', help='Slogan da loja')
    parser.add_argument('--cor', default='', help='Cor primária, ex: #16a34a')
    parser.add_argument('--base', default='main', help='Branch de origem (padrão: main)')
    args = parser.parse_args()

    slug = args.slug or slugify(args.nome)
    if not slug:
        sys.exit('Não foi possível gerar um identificador a partir do nome. Use --slug.')
    branch = f'cliente/{slug}'

    if git_output('status', '--porcelain'):
        sys.exit('Existem alterações não salvas no git. Faça commit ou descarte antes de criar um cliente.')
    if git_output('branch', '--list', branch):
        sys.exit(f'A branch {branch} já existe.')

    print(f'\n[1/5] Criando branch {branch} a partir de {args.base}...')
    run(['git', 'switch', '-c', branch, args.base])

    print('\n[2/5] Removendo fotos, logos e ícones do cliente anterior...')
    old_files = []
    for folder in CLIENT_MEDIA_DIRS + [CLIENT_ICONS_DIR]:
        old_files += tracked_files_in(folder)
    if old_files:
        run(['git', 'rm', '-q', '--', *old_files])
    for folder in CLIENT_MEDIA_DIRS:
        shutil.rmtree(PROJECT_DIR / folder, ignore_errors=True)

    print('\n[3/5] Criando banco de dados limpo...')
    db_path = PROJECT_DIR / 'db.sqlite3'
    if db_path.exists():
        db_path.unlink()
    python = find_python()
    # DEBUG só durante a criação: dispensa .env com chave secreta neste passo.
    env = dict(os.environ, DB_ENGINE='sqlite', DJANGO_DEBUG='true')
    run([python, 'manage.py', 'migrate', '--noinput'], env=env)

    print('\n[4/5] Configurando loja e usuário gerente...')
    password = secrets.token_urlsafe(9)
    env['NABANDEJA_INIT_ADMIN_PASSWORD'] = password
    run([python, 'manage.py', 'ensure_initial_access'], env=env)
    configure = (
        'from restaurante.models import AppSettings\n'
        's = AppSettings.get_settings()\n'
        f's.store_name = {args.nome!r}\n'
        + (f's.slogan = {args.slogan!r}\n' if args.slogan else '')
        + (f's.primary_color = {args.cor!r}\n' if args.cor else '')
        + 's.save()\n'
    )
    run([python, 'manage.py', 'shell', '-c', configure], env=env)

    print('\n[5/5] Salvando cliente no git...')
    run(['git', 'add', '-f', 'db.sqlite3'])
    run(['git', 'add', '-A'])
    run(['git', 'commit', '-q', '-m', f'cliente: {args.nome}'])

    print(f"""
========================================
 Cliente criado: {args.nome}
========================================
 Branch:  {branch}
 Login:   gerente
 Senha:   {password}   <- anote agora, ela não fica salva em lugar nenhum

 Próximos passos:
   - Envie o logo em Configurações (o atalho da Área de Trabalho usa ele)
   - Para enviar ao GitHub:  git push -u origin {branch}
   - Para trazer melhorias da main:  git switch {branch}  e  git merge main
""")


if __name__ == '__main__':
    main()
