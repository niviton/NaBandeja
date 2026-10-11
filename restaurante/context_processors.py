from django.conf import settings

from .models import AppSettings
from .services import license


ADMIN_NAV = [
    ('admin_dashboard', 'Painel', 'bi-grid-1x2', 'dashboard'),
    ('admin_reports', 'Relatórios', 'bi-bar-chart', 'reports'),
    ('admin_menu', 'Cardápio', 'bi-bag', 'menu'),
    ('admin_ingredients', 'Ingredientes', 'bi-box-seam', 'ingredients'),
    ('admin_tables', 'Mesas e QR Code', 'bi-grid-3x3', 'tables'),
    ('admin_online_orders', 'Delivery e online', 'bi-scooter', 'online'),
    ('expenses', 'Contas a pagar', 'bi-wallet2', 'expenses'),
    ('admin_users', 'Equipe', 'bi-people', 'users'),
    ('admin_settings', 'Configurações', 'bi-gear', 'settings'),
    ('system_status', 'Sistema', 'bi-hdd-stack', 'system'),
]


def settings_processor(request):
    """Disponibiliza as configurações da loja em todos os templates."""
    store = AppSettings.get_settings()
    return {
        'app_settings': store,
        'license_status': license.status(store.license_key),
        'google_login_enabled': settings.GOOGLE_LOGIN_ENABLED,
        'nabandeja_version': settings.NABANDEJA_VERSION,
        'admin_nav': ADMIN_NAV,
    }
