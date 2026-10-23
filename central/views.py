"""Login geral (escolhe a loja pelo campo Empresa) e painel central do administrador do servidor."""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from restaurante import security
from restaurante.forms import LoginForm
from restaurante.services.company import normalize

from . import services, tenancy
from .models import Loja


def central_admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and user.is_superuser and not request.session.get(tenancy.SESSION_KEY)):
            return redirect('login')
        return view(request, *args, **kwargs)
    return wrapper


def _store_home(loja):
    return loja.url('/dashboard/')


@never_cache
@transaction.non_atomic_requests
def login_view(request):
    if request.user.is_authenticated and not request.session.get(tenancy.SESSION_KEY):
        if request.user.is_superuser:
            return redirect('central_home')
        logout(request)

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        empresa = normalize(request.POST.get('empresa', ''))
        username = request.POST.get('username', '')
        lock_name = f'{empresa}:{username}'
        if security.is_locked(request, lock_name):
            messages.error(request, 'Muitas tentativas erradas. Aguarde alguns minutos e tente de novo.')
        elif empresa == normalize(settings.CENTRAL_CODE):
            if form.is_valid() and form.get_user().is_superuser:
                security.reset(request, lock_name)
                login(request, form.get_user())
                tenancy.mark_login(request)
                return redirect('central_home')
            security.register_failure(request, lock_name)
            messages.error(request, 'Empresa, usuário ou senha incorretos.')
        else:
            loja = Loja.objects.filter(code_key=empresa, is_active=True).first() if empresa else None
            if loja is None:
                security.register_failure(request, lock_name)
                messages.error(request, 'Empresa, usuário ou senha incorretos.')
            else:
                with tenancy.using(loja):
                    form = LoginForm(request, data=request.POST)
                    if form.is_valid():
                        security.reset(request, lock_name)
                        user = form.get_user()
                        login(request, user)
                        tenancy.mark_login(request)
                        messages.success(request, f'Bem-vindo, {user.first_name or user.username}!')
                        return HttpResponseRedirect(_store_home(loja))
                security.register_failure(request, lock_name)
                messages.error(request, 'Empresa, usuário ou senha incorretos.')

    return render(request, 'restaurante/login.html', {'form': form, 'central_login': True, 'empresa_fixa': ''})


def logout_view(request):
    logout(request)
    messages.info(request, 'Você saiu do sistema.')
    return redirect('login')


@central_admin_required
def home(request):
    lojas = list(Loja.objects.all())
    for loja in lojas:
        path = tenancy.database_path(loja.code)
        loja.size_kb = path.stat().st_size // 1024 if path.exists() else 0
    return render(request, 'central/home.html', {'lojas': lojas, 'base_url': request.build_absolute_uri('/').rstrip('/')})


@central_admin_required
@transaction.non_atomic_requests
def new_store(request):
    data = request.POST if request.method == 'POST' else {}
    if request.method == 'POST':
        try:
            loja = services.create_store(
                data.get('name'), data.get('code'), data.get('username'), data.get('password'),
                first_name=data.get('first_name', ''),
            )
        except services.StoreError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'Loja "{loja.name}" criada. Mande para o gerente: endereço, empresa "{loja.code}", usuário e senha.')
            return redirect('central_home')
    return render(request, 'central/new.html', {'data': data})


@central_admin_required
@require_POST
@transaction.non_atomic_requests
def enter_store(request, code):
    """Entra na loja como suporte (usuário 'nabandeja' da loja, superusuário)."""
    loja = get_object_or_404(Loja, code=code, is_active=True)
    with tenancy.using(loja):
        user = services.support_user(loja)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        tenancy.mark_login(request)
    return HttpResponseRedirect(_store_home(loja))


@central_admin_required
@require_POST
def toggle_store(request, code):
    loja = get_object_or_404(Loja, code=code)
    loja.is_active = not loja.is_active
    loja.save(update_fields=['is_active'])
    if loja.is_active:
        messages.success(request, f'{loja.name} reativada.')
    else:
        messages.warning(request, f'{loja.name} desativada: ninguém da loja consegue entrar.')
    return redirect('central_home')
