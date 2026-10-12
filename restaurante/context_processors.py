from django.conf import settings

from . import realtime
from .models import AppSettings
from .modules import enabled_modules
from .services import backup_remoto, license

# Gestão, em grupos: (título, [(rota, rótulo, ícone, chave do menu ativo, módulo exigido)])
ADMIN_NAV = [
    ('Vendas', [
        ('admin_reports', 'Relatórios', 'bi-bar-chart', 'reports', None),
        ('cash_history', 'Caixas', 'bi-cash-stack', 'cash', 'caixa'),
        ('expenses', 'Contas a pagar', 'bi-wallet2', 'expenses', 'financeiro'),
    ]),
    ('Cardápio', [
        ('admin_menu', 'Produtos', 'bi-journal-text', 'menu', None),
        ('admin_ingredients', 'Ingredientes', 'bi-box-seam', 'ingredients', 'ingredientes'),
    ]),
    ('Loja', [
        ('admin_tables', 'Mesas e QR Code', 'bi-grid-3x3', 'tables', None),
        ('admin_users', 'Equipe', 'bi-people', 'users', None),
        ('admin_settings', 'Configurações', 'bi-sliders', 'settings', None),
    ]),
    ('Sistema', [
        ('system_status', 'Backup e licença', 'bi-hdd-stack', 'system', None),
    ]),
]


def _visible(requirement, modules):
    if requirement is None:
        return True
    if isinstance(requirement, tuple):
        return any(modules[key] for key in requirement)
    return modules[requirement]


def settings_processor(request):
    """Disponibiliza as configurações da loja em todos os templates."""
    store = AppSettings.get_settings()
    modules = enabled_modules(store)
    return {
        'app_settings': store,
        'modules': modules,
        'license_status': license.status(store.license_key),
        'google_login_enabled': settings.GOOGLE_LOGIN_ENABLED and modules['google'],
        # Botão aparece mesmo sem credenciais; nesse caso explica o que falta.
        'google_login_visible': modules['google'],
        'nabandeja_version': settings.NABANDEJA_VERSION,
        'admin_nav': [
            (title, [item[:4] for item in items if _visible(item[4], modules)]) for title, items in ADMIN_NAV
        ],
        'delivery_enabled': modules['delivery'] or modules['online'],
        'is_master': settings.IS_MASTER,
        'espelho_nome': settings.ESPELHO_NOME,
        'espelho_master_url': settings.ESPELHO_MASTER_URL,
        'somente_leitura': settings.SOMENTE_LEITURA,
        'backup_remoto': _remote_backup_status(request),
        'realtime_transport': realtime.transport(),
        'realtime_poll_seconds': settings.REALTIME_POLL_SECONDS,
        'realtime_cursor': realtime.latest_cursor,  # só consulta o banco se o template usar
    }


def _remote_backup_status(request):
    """Situação do backup externo, só para o rodapé do gerente."""
    user = getattr(request, 'user', None)
    if settings.IS_MASTER or settings.ESPELHO_NOME or not (user and user.is_authenticated and user.role == 'gerente'):
        return None
    return backup_remoto.status()
