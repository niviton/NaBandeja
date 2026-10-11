from importlib import import_module

from django.apps import AppConfig


class RestauranteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'restaurante'
    verbose_name = 'Gestão do Restaurante'

    def ready(self):
        import_module(f'{self.name}.signals')  # registra os avisos de tempo real
