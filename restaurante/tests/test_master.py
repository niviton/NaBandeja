"""Painel master: cofre, backup externo (git local), empresas, views e modo somente leitura."""

import io
import json
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from restaurante.models import User
from restaurante.services import backup_remoto, cofre, master
from restaurante.services.espelho import SSO_SALT
from restaurante.views import support

from . import factories as f

HAS_GIT = shutil.which('git') is not None


def make_db(path, store_name='Loja Teste'):
    """Banco SQLite mínimo com as tabelas que o resumo do painel lê."""
    connection = sqlite3.connect(path)
    connection.executescript(f"""
        CREATE TABLE restaurante_appsettings (id INTEGER PRIMARY KEY, store_name TEXT, company_code TEXT);
        INSERT INTO restaurante_appsettings VALUES (1, '{store_name}', 'loja-teste');
        CREATE TABLE restaurante_order (id INTEGER PRIMARY KEY, status TEXT, total REAL, closed_at TEXT, created_at TEXT);
        INSERT INTO restaurante_order VALUES (1, 'finalizado', 42.5, datetime('now'), datetime('now'));
        CREATE TABLE restaurante_user (id INTEGER PRIMARY KEY, is_active INT, is_superuser INT);
        INSERT INTO restaurante_user VALUES (1, 1, 0);
        CREATE TABLE restaurante_product (id INTEGER PRIMARY KEY);
    """)
    connection.commit()
    connection.close()


class TempDirMixin:
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)


# ------------------------------------------------------------------ cofre

class CofreTests(TestCase):
    def test_ida_e_volta(self):
        pem, public = cofre.generate_master_key()
        blob = cofre.encrypt(b'dados da loja', public)
        self.assertTrue(blob.startswith(cofre.MAGIC))
        self.assertNotIn(b'dados da loja', blob)
        self.assertEqual(cofre.decrypt(blob, cofre.load_private_key(pem)), b'dados da loja')

    def test_chave_errada_falha(self):
        _, public = cofre.generate_master_key()
        other_pem, _ = cofre.generate_master_key()
        with self.assertRaises(cofre.CofreError):
            cofre.decrypt(cofre.encrypt(b'x', public), cofre.load_private_key(other_pem))

    def test_arquivo_adulterado_falha(self):
        pem, public = cofre.generate_master_key()
        blob = bytearray(cofre.encrypt(b'segredo', public))
        blob[-1] ^= 1
        with self.assertRaises(cofre.CofreError):
            cofre.decrypt(bytes(blob), cofre.load_private_key(pem))

    def test_chave_ssh_de_envio(self):
        private, public_line = cofre.generate_ssh_key('nabandeja-teste')
        self.assertIn(b'OPENSSH PRIVATE KEY', private)
        self.assertTrue(public_line.startswith('ssh-ed25519 '))
        self.assertTrue(public_line.endswith(' nabandeja-teste'))


# ------------------------------------------------------------------ pacote e git

class ArchiveTests(TempDirMixin, TestCase):
    def test_banco_e_fotos_ida_e_volta(self):
        make_db(self.tmp / 'db.sqlite3')
        media = self.tmp / 'media' / 'products'
        media.mkdir(parents=True)
        (media / 'x.jpg').write_bytes(b'foto')
        data = backup_remoto.build_archive(self.tmp / 'db.sqlite3', self.tmp / 'media')
        target = self.tmp / 'restaurado'
        db = backup_remoto.extract_archive(data, target)
        self.assertEqual(master.resumo_banco(db)['loja'], 'Loja Teste')
        self.assertEqual((target / 'media' / 'products' / 'x.jpg').read_bytes(), b'foto')

    def test_recusa_caminho_fora_da_pasta(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('db.sqlite3', b'x')
            archive.writestr('media/../../fora.txt', b'x')
        with self.assertRaises(backup_remoto.BackupError):
            backup_remoto.extract_archive(buffer.getvalue(), self.tmp / 'destino')
        self.assertFalse((self.tmp / 'fora.txt').exists())


@override_settings(NABANDEJA_VERSION='9.9.9')
class GitPublishTests(TempDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        if not HAS_GIT:
            self.skipTest('git não instalado')
        self.remote = self.tmp / 'remoto.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.remote)], check=True)

    def test_publica_busca_e_mantem_so_os_ultimos_dias(self):
        from datetime import date
        work = self.tmp / 'loja'
        for day in (1, 2, 3):
            blob = f'backup {day}'.encode()
            backup_remoto.publish(work, str(self.remote), blob, backup_remoto.make_manifest(blob, 'loja'),
                                  keep_days=2, today=date(2026, 1, day))
        fetched = backup_remoto.fetch(self.tmp / 'master', str(self.remote))
        self.assertEqual(fetched['atual'], b'backup 3')
        self.assertEqual(fetched['manifest']['origem'], 'loja')
        self.assertEqual(fetched['diarios'], ['2026-01-03.nbk', '2026-01-02.nbk'])
        self.assertEqual(backup_remoto.read_daily(self.tmp / 'master', '2026-01-02.nbk'), b'backup 2')
        # Sem histórico: o repositório guarda só o último commit.
        log = subprocess.run(['git', '--git-dir', str(self.remote), 'rev-list', '--count', 'main'],
                             capture_output=True, text=True, check=True)
        self.assertEqual(log.stdout.strip(), '1')

    def test_ponto_de_restauracao_invalido(self):
        with self.assertRaises(backup_remoto.BackupError):
            backup_remoto.read_daily(self.tmp, '../atual.nbk')


# ------------------------------------------------------------------ empresas

class MasterServiceTests(TempDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        if not HAS_GIT:
            self.skipTest('git não instalado')
        self.override = override_settings(MASTER_DIR=self.tmp / 'master', REPOS_DIR=str(self.tmp / 'repos'),
                                          GITHUB_TOKEN='', GITHUB_OWNER='')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_criar_empresa_completa(self):
        empresa = master.criar('Pizzaria do João', '', 'gerente', 'senha-forte-123',
                               {'delivery': True, 'pix': False})
        self.assertEqual(empresa.codigo, 'pizzaria-do-joao')
        self.assertEqual(empresa.situacao[0], 'implantacao')
        self.assertTrue(empresa.tem_repositorio)
        self.assertEqual(empresa.resumo['loja'], 'Pizzaria do João')
        self.assertEqual(empresa.resumo['codigo_login'], 'pizzaria-do-joao')
        self.assertEqual(empresa.resumo['equipe'], 1)
        self.assertTrue(empresa.ssh_key.exists())

        # O primeiro backup (do master) abre só com a chave mestra.
        fetched = backup_remoto.fetch(self.tmp / 'conferencia', empresa.data['repo_master'])
        self.assertEqual(fetched['manifest']['origem'], 'master')
        data = cofre.decrypt(fetched['atual'], master.master_private_key())
        self.assertIn('db.sqlite3', zipfile.ZipFile(io.BytesIO(data)).namelist())

        with self.assertRaises(master.MasterError):
            master.criar('Outra', 'pizzaria-do-joao', 'gerente', 'senha-forte-123', {})

        # Instalador: .env apontando para o repositório da loja, chave de envio e banco.
        package = zipfile.ZipFile(master.gerar_pacote(empresa))
        self.assertTrue({'.env', 'chave-backup', 'db.sqlite3', 'LEIA-ME-INSTALACAO.txt'} <= set(package.namelist()))
        env_text = package.read('.env').decode()
        self.assertIn(f'NABANDEJA_BACKUP_REPO={empresa.data["repo_loja"]}', env_text)
        self.assertIn(f'NABANDEJA_BACKUP_CHAVE_PUBLICA={master.master_public_key()}', env_text)
        self.assertIn('DJANGO_DEBUG=false', env_text)

    def test_backup_da_loja_vira_espelho_e_bloqueia_publicar(self):
        empresa = master.criar('Bar do Zé', 'bar-do-ze', 'gerente', 'senha-forte-123', {})
        # A loja envia o backup dela (como o backup_remoto.run() faz no PC do cliente).
        loja = self.tmp / 'pc-da-loja'
        loja.mkdir()
        make_db(loja / 'db.sqlite3', store_name='Bar do Zé (loja)')
        blob = cofre.encrypt(backup_remoto.build_archive(loja / 'db.sqlite3', loja / 'media'), master.master_public_key())
        backup_remoto.publish(loja / 'repo', empresa.data['repo_loja'], blob, backup_remoto.make_manifest(blob, 'loja'))

        master.atualizar(empresa)
        empresa = master.obter('bar-do-ze')
        self.assertEqual(empresa.situacao[0], 'ativa')
        self.assertEqual(empresa.resumo['loja'], 'Bar do Zé (loja)')
        self.assertEqual(empresa.resumo['vendas_30d'], 42.5)
        self.assertTrue((empresa.espelho / 'db.sqlite3').exists())
        with self.assertRaises(master.MasterError):
            master.publicar(empresa)
        # Reinstalação usa o último backup da loja.
        package = zipfile.ZipFile(master.gerar_pacote(empresa))
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'db.sqlite3').write_bytes(package.read('db.sqlite3'))
            self.assertEqual(master.resumo_banco(Path(tmp, 'db.sqlite3'))['loja'], 'Bar do Zé (loja)')

    def test_importar_arquivo_que_nao_e_banco(self):
        fake = SimpleUploadedFile('db.sqlite3', b'nao sou um banco')
        with self.assertRaises(master.MasterError):
            master.criar('Importada', '', 'gerente', 'senha-forte-123', {}, banco_importado=fake)
        self.assertFalse((self.tmp / 'master' / 'empresas' / 'importada').exists())

    def test_obter_recusa_codigo_invalido(self):
        for codigo in ('', '../chaves', 'NAO-EXISTE'):
            with self.assertRaises(master.MasterError):
                master.obter(codigo)


@override_settings(GITHUB_TOKEN='tok', GITHUB_OWNER='niviton')
class GithubTests(TestCase):
    def test_cria_repositorio_privado_e_deploy_key(self):
        calls = []

        def fake(method, path, payload=None):
            calls.append((method, path, payload))
            if path == '/user':
                return 200, {'login': 'niviton'}
            if path == '/user/repos':
                return 201, {'private': True}
            return 201, {}

        with mock.patch.object(master, '_github', side_effect=fake):
            loja, painel = master._create_github_repo('nabandeja-dados-x', 'ssh-ed25519 AAA x', 'X')
        self.assertEqual(loja, 'git@github.com:niviton/nabandeja-dados-x.git')
        self.assertEqual(painel, 'https://github.com/niviton/nabandeja-dados-x.git')
        self.assertTrue(calls[1][2]['private'])
        key_call = calls[2]
        self.assertEqual(key_call[1], '/repos/niviton/nabandeja-dados-x/keys')
        self.assertFalse(key_call[2]['read_only'])

    def test_recusa_repositorio_publico(self):
        def fake(method, path, payload=None):
            if path == '/user':
                return 200, {'login': 'niviton'}
            if method == 'POST':
                return 422, {'message': 'name already exists'}
            return 200, {'private': False}

        with mock.patch.object(master, '_github', side_effect=fake):
            with self.assertRaisesMessage(master.MasterError, 'PÚBLICO'):
                master._create_github_repo('nabandeja-dados-x', 'ssh-ed25519 AAA x', 'X')

    def test_token_recusado(self):
        with mock.patch.object(master, '_github', return_value=(401, {})):
            with self.assertRaises(master.MasterError):
                master._create_github_repo('nabandeja-dados-x', 'k', 'X')


# ------------------------------------------------------------------ views e modos

class MasterViewTests(TempDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.override = override_settings(IS_MASTER=True, MASTER_DIR=self.tmp, REPOS_DIR='', GITHUB_TOKEN='')
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.admin = User.objects.create_user('dono@exemplo.com', password='senha-forte-123', is_superuser=True,
                                              is_staff=True, role='gerente')

    def login(self, username, password='senha-forte-123'):
        return self.client.post(reverse('login'), {'username': username, 'password': password})

    def test_login_master_sem_empresa(self):
        response = self.login('dono@exemplo.com')
        self.assertRedirects(response, reverse('master_home'))
        page = self.client.get(reverse('master_home'))
        self.assertContains(page, 'Nenhuma empresa ainda')
        self.assertContains(page, 'Backup externo não configurado')

    def test_login_master_recusa_quem_nao_e_superusuario(self):
        f.user('gerente')
        response = self.login('gerente')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_rotas_da_loja_redirecionam_para_o_painel(self):
        self.login('dono@exemplo.com')
        self.assertRedirects(self.client.get('/garcom/'), reverse('master_home'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/admin/'), reverse('master_home'), fetch_redirect_response=False)

    def test_empresa_inexistente(self):
        self.login('dono@exemplo.com')
        response = self.client.get(reverse('master_empresa', args=['nao-existe']))
        self.assertRedirects(response, reverse('master_home'))

    def test_painel_so_no_modo_master(self):
        self.login('dono@exemplo.com')
        with override_settings(IS_MASTER=False):
            self.assertEqual(self.client.get(reverse('master_home')).status_code, 403)


@override_settings(IS_MASTER=False, SOMENTE_LEITURA=True)
class ReadOnlyTests(TestCase):
    def test_bloqueia_alteracoes(self):
        manager = f.user()
        f.open_store()
        self.client.force_login(manager)
        response = self.client.post(reverse('toggle_store_status'), HTTP_REFERER='http://testserver/admin-panel/')
        self.assertRedirects(response, 'http://testserver/admin-panel/', fetch_redirect_response=False)
        self.assertTrue(f.open_store().is_store_open)
        htmx = self.client.post(reverse('toggle_store_status'), HTTP_HX_REQUEST='true')
        self.assertEqual(htmx.status_code, 403)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)


@override_settings(ESPELHO_SSO_KEY='chave-de-teste')
class EspelhoLoginTests(TestCase):
    def setUp(self):
        support._used_tokens.clear()

    def token(self, key='chave-de-teste'):
        return signing.dumps({'n': 'x'}, key=key, salt=SSO_SALT)

    def test_entra_como_suporte_uma_vez(self):
        f.open_store()
        token = self.token()
        response = self.client.get(reverse('espelho_login', args=[token]))
        self.assertRedirects(response, reverse('admin_dashboard'), fetch_redirect_response=False)
        user = User.objects.get(username='nabandeja')
        self.assertTrue(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.client.logout()
        self.assertEqual(self.client.get(reverse('espelho_login', args=[token])).status_code, 403)

    def test_token_com_outra_chave(self):
        self.assertEqual(self.client.get(reverse('espelho_login', args=[self.token('outra')])).status_code, 403)

    @override_settings(ESPELHO_SSO_KEY='')
    def test_desligado_fora_do_espelho(self):
        self.assertEqual(self.client.get(reverse('espelho_login', args=[self.token()])).status_code, 404)


class SaveDataTests(TestCase):
    @override_settings(BACKUP_REMOTO_REPO='', BACKUP_REMOTO_CHAVE_PUBLICA='')
    def test_sem_configuracao(self):
        f.open_store()
        self.client.force_login(f.user())
        response = self.client.post(reverse('save_data'), follow=True)
        self.assertContains(response, 'ainda não foi configurado')

    @override_settings(BACKUP_REMOTO_REPO='repo', BACKUP_REMOTO_CHAVE_PUBLICA='chave')
    def test_dispara_em_segundo_plano(self):
        f.open_store()
        self.client.force_login(f.user())
        with mock.patch.object(backup_remoto, 'run_in_background', return_value=True) as started:
            response = self.client.post(reverse('save_data'), follow=True)
        started.assert_called_once()
        self.assertContains(response, 'Salvando os dados')

    def test_garcom_nao_pode(self):
        f.open_store()
        self.client.force_login(f.user('ana', role='garcom'))
        response = self.client.post(reverse('save_data'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('save_data', response.url)

    def test_rodape_mostra_situacao_para_o_gerente(self):
        f.open_store()
        self.client.force_login(f.user())
        with override_settings(BACKUP_REMOTO_REPO='', BACKUP_REMOTO_CHAVE_PUBLICA=''):
            self.assertContains(self.client.get(reverse('admin_dashboard')), 'Backup externo não configurado')


class RemoteBackupRunTests(TempDirMixin, TestCase):
    def test_loja_envia_backup_criptografado(self):
        if not HAS_GIT:
            self.skipTest('git não instalado')
        remote = self.tmp / 'remoto.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        pem, public = cofre.generate_master_key()
        db = self.tmp / 'db.sqlite3'
        make_db(db)
        with override_settings(DATA_DIR=self.tmp, BACKUP_REMOTO_REPO=str(remote), BACKUP_REMOTO_CHAVE_PUBLICA=public,
                               BACKUP_REMOTO_CHAVE_SSH=self.tmp / 'nao-existe', MEDIA_ROOT=self.tmp / 'media'), \
                mock.patch.object(backup_remoto, 'db_path', return_value=db):
            self.assertTrue(backup_remoto.run())
            status = backup_remoto.status()
        self.assertIsNotNone(status['ultimo_ok'])
        self.assertEqual(status['erro'], '')
        fetched = backup_remoto.fetch(self.tmp / 'master', str(remote))
        self.assertEqual(fetched['manifest']['origem'], 'loja')
        archive = zipfile.ZipFile(io.BytesIO(cofre.decrypt(fetched['atual'], cofre.load_private_key(pem))))
        self.assertIn('db.sqlite3', archive.namelist())

    def test_erro_fica_registrado(self):
        _, public = cofre.generate_master_key()
        db = self.tmp / 'db.sqlite3'
        make_db(db)
        with override_settings(DATA_DIR=self.tmp, BACKUP_REMOTO_REPO=str(self.tmp / 'nao-existe.git'),
                               BACKUP_REMOTO_CHAVE_PUBLICA=public, MEDIA_ROOT=self.tmp / 'media'), \
                mock.patch.object(backup_remoto, 'db_path', return_value=db):
            self.assertFalse(backup_remoto.run())
            self.assertTrue(backup_remoto.status()['erro'])
        saved = json.loads((self.tmp / 'backups' / 'remoto' / 'status.json').read_text(encoding='utf-8'))
        self.assertNotIn('ultimo_ok', saved)
