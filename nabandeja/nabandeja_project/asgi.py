"""
ASGI config for nabandeja_project project.
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')

from django.core.asgi import get_asgi_application


django_asgi_app = get_asgi_application()

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from nabandeja_project.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            'http': django_asgi_app,
            'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        }
    )
except Exception:
    application = django_asgi_app
