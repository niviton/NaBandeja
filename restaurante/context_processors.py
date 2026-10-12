from django.conf import settings

from .models import AppSettings
from .modules import enabled_modules
from .services import license

# (rota, rótulo, ícone, chave do menu ativo, módulo exigido)
ADMIN_NAV = [
    ('admin_dashboard', 'Painel', 'bi-grid-1x2', 'dashboard', None),
    ('admin_reports', 'Relatórios', 'bi-bar-chart', 'reports', None),
    ('admin_menu', 'Cardápio', 'bi-journal-text', 'menu', None),
    ('admin_ingredients', 'Ingredientes', 'bi-box-seam', 'ingredients', 'ingredientes'),
    ('admin_tables', 'Mesas e QR Code', 'bi-grid-3x3', 'tables', None),
    ('admin_online_orders', 'Delivery e online', 'bi-scooter', 'online', ('delivery', 'online')),
    ('expenses', 'Contas a pagar', 'bi-wallet2', 'expenses', 'financeiro'),
    ('admin_users', 'Equipe', 'bi-people', 'users', None),
    ('admin_settings', 'Configurações', 'bi-sliders', 'settings', None),
    ('system_status', 'Sistema', 'bi-hdd-stack', 'system', None),
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
        'nabandeja_version': settings.NABANDEJA_VERSION,
        'admin_nav': [item[:4] for item in ADMIN_NAV if _visible(item[4], modules)],
    }
