from django.apps import AppConfig


class RestauranteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'restaurante'
    verbose_name = 'Gestão do Restaurante'

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
