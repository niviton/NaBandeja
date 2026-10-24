"""Manual do sistema (botão Ajuda), aberto para toda a equipe."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def help_page(request):
    return render(request, 'app/ajuda.html', {'active_tab': 'ajuda'})
