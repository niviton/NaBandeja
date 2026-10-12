"""
WSGI: só HTTP (PythonAnywhere, servidores WSGI). Sem WebSocket: o tempo real
usa polling (restaurante/realtime.py).
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nabandeja_project.settings')
os.environ.setdefault('NABANDEJA_SERVIDOR', 'wsgi')

application = get_wsgi_application()
