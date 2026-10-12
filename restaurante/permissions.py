"""Controle de acesso por função (garçom, cozinha, gerente)."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect

from .models import Order

HOME_BY_ROLE = {
    'gerente': 'admin_dashboard',
    'cozinha': 'kitchen_view',
    'garcom': 'waiter_view',
}


def home_for(user):
    return HOME_BY_ROLE.get(getattr(user, 'role', ''), 'waiter_view')


def wants_json(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.headers.get('HX-Request') == 'true'
        or 'application/json' in request.headers.get('Accept', '')
        or request.path.startswith('/api/')
    )


def role_required(*roles):
    """
    Exige login e uma das funções informadas.
    Ex.: @role_required('gerente')  ou  @role_required('garcom', 'gerente')
    """
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                if wants_json(request):
                    return JsonResponse({'success': False, 'message': 'Acesso não autorizado.'}, status=403)
                messages.error(request, 'Acesso não autorizado.')
                return redirect(home_for(request.user))
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


manager_required = role_required('gerente')


def support_required(view):
    """Só o superusuário do suporte NaBandeja."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Área do suporte NaBandeja.')
        return view(request, *args, **kwargs)
    return wrapper
service_required = role_required('garcom', 'gerente')
kitchen_required = role_required('cozinha', 'gerente')


def can_access_order(user, order):
    if user.role == 'gerente':
        return True
    if user.role == 'garcom':
        # Garçom atende qualquer mesa do salão; delivery fica com quem lançou.
        return order.order_type == 'dine-in' or order.waiter_id == user.id
    return False


def get_order_or_403(user, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(user, order):
        raise PermissionDenied('Você não tem permissão para acessar este pedido.')
    return order
