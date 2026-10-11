"""Registro de auditoria de ações sensíveis."""

import logging

from django.conf import settings

from ..models import AuditLog

logger = logging.getLogger('nabandeja.audit')


def client_ip(request):
    # X-Forwarded-For só é confiável atrás de um proxy configurado.
    if settings.USE_X_FORWARDED_HOST or getattr(settings, 'SECURE_PROXY_SSL_HEADER', None):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def audit(request, action, description='', obj=None, **metadata):
    user = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=type(obj).__name__ if obj is not None else '',
        object_id=str(getattr(obj, 'pk', '') or ''),
        description=description,
        metadata={key: str(value) for key, value in metadata.items()},
        ip_address=client_ip(request),
    )
    logger.info('%s | %s | %s', getattr(user, 'username', '-'), action, description)
