"""Polling do tempo real: funciona em qualquer servidor (WSGI ou ASGI)."""

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .. import realtime


@never_cache
@require_GET
def realtime_events(request):
    """GET /tempo-real/eventos/?desde=<id> -> eventos depois desse id."""
    if not request.user.is_authenticated:
        return JsonResponse({'login': True}, status=401)
    try:
        cursor = int(request.GET['desde'])
    except (KeyError, ValueError):
        cursor = None
    return JsonResponse(realtime.events_since(cursor))
