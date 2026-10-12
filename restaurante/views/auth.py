from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from .. import security
from ..models import AppSettings
from ..services import company
from ..forms import LoginForm
from ..permissions import home_for


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(home_for(request.user))

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username', '')
        if security.is_locked(request, username):
            messages.error(request, 'Muitas tentativas erradas. Aguarde alguns minutos e tente de novo.')
        elif not company.matches(request.POST.get('empresa', ''), AppSettings.get_settings()):
            security.register_failure(request, username)
            messages.error(request, 'Empresa, usuário ou senha incorretos.')
        elif form.is_valid():
            security.reset(request, username)
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bem-vindo, {user.first_name or user.username}!')
            return redirect(home_for(user))
        else:
            security.register_failure(request, username)
            messages.error(request, 'Empresa, usuário ou senha incorretos.')

    return render(request, 'restaurante/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Você saiu do sistema.')
    return redirect('login')


@login_required
def dashboard(request):
    return redirect(home_for(request.user))
