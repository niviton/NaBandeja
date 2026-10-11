from .models import AppSettings


def settings_processor(request):
    """Context processor para disponibilizar as configurações em todos os templates"""
    return {
        'app_settings': AppSettings.get_settings()
    }
