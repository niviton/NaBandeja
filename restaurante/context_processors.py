from django.conf import settings

from .models import AppSettings


def settings_processor(request):
    """Disponibiliza as configurações da loja em todos os templates."""
    return {
        'app_settings': AppSettings.get_settings(),
        'google_login_enabled': settings.GOOGLE_LOGIN_ENABLED,
        'nabandeja_version': settings.NABANDEJA_VERSION,
    }
