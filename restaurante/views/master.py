"""Painel master: empresas, backups, entrar na empresa e pacotes de instalação."""

import secrets

from django import forms
from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from ..modules import MODULES
from ..permissions import master_required
from ..services import espelho, master
from ..services.master import MasterError


class EmpresaForm(forms.Form):
    nome = forms.CharField(max_length=200, label='Nome da empresa')
    codigo = forms.CharField(max_length=40, required=False, label='Código de login')
    gerente_usuario = forms.CharField(max_length=150, initial='gerente', label='Usuário do gerente')
    gerente_senha = forms.CharField(max_length=128, required=False, label='Senha do gerente')
    banco = forms.FileField(required=False, label='Importar banco existente (db.sqlite3)')

    def clean_codigo(self):
        codigo = master.normalizar_codigo(self.cleaned_data.get('codigo') or self.data.get('nome', ''))
        if not codigo:
            raise forms.ValidationError('Use letras ou números no código.')
        return codigo

    def clean_gerente_senha(self):
        senha = self.cleaned_data.get('gerente_senha', '')
        if senha and len(senha) < 8:
            raise forms.ValidationError('Use pelo menos 8 caracteres (ou deixe em branco para gerar).')
        return senha


def _empresa_or_redirect(request, codigo):
    try:
        return master.obter(codigo)
    except MasterError as exc:
        messages.error(request, str(exc))
        return None


@never_cache
@master_required
def master_home(request):
    empresas = master.listar()
    counts = {}
    for empresa in empresas:
        key = empresa.situacao[0]
        counts[key] = counts.get(key, 0) + 1
    return render(request, 'master/home.html', {
        'empresas': empresas,
        'abertas': espelho.abertas(),
        'counts': counts,
        'remote_mode': master.remote_mode(),
        'has_master_key': master.has_master_key(),
        'key_path': master.private_key_path(),
        'active': 'home',
    })


@never_cache
@master_required
def empresa_nova(request):
    form = EmpresaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        senha = data['gerente_senha'] or secrets.token_urlsafe(9)
        modulos = {key: f'module_{key}' in request.POST for key, _, _ in MODULES}
        try:
            empresa = master.criar(
                data['nome'], data['codigo'], data['gerente_usuario'].strip(), senha, modulos,
                banco_importado=data['banco'],
            )
        except MasterError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'Empresa {empresa.nome} criada. Gerente: {data["gerente_usuario"]} · senha: {senha}'
                                      + ('' if data['gerente_senha'] else '  (anote agora: ela não fica salva)'))
            if empresa.data.get('erro'):
                messages.warning(request, f'Backup ainda não configurado: {empresa.data["erro"]}')
            return redirect('master_empresa', codigo=empresa.codigo)
    return render(request, 'master/nova.html', {
        'form': form,
        'modules': [(key, label, help_text, request.method != 'POST' or f'module_{key}' in request.POST)
                    for key, label, help_text in MODULES],
        'remote_mode': master.remote_mode(),
        'active': 'new',
    })


@never_cache
@master_required
def empresa_detalhe(request, codigo):
    empresa = _empresa_or_redirect(request, codigo)
    if empresa is None:
        return redirect('master_home')
    return render(request, 'master/empresa.html', {
        'empresa': empresa,
        'aberta': codigo in espelho.abertas(),
        'remote_mode': master.remote_mode(),
    })


@master_required
@require_POST
def atualizar(request, codigo=None):
    if codigo:
        empresa = _empresa_or_redirect(request, codigo)
        if empresa is None:
            return redirect('master_home')
        empresas = [empresa]
    else:
        empresas = master.listar()
    ok, falhas = 0, []
    for empresa in empresas:
        if not empresa.tem_repositorio:
            continue
        try:
            master.atualizar(empresa)
            ok += 1
        except MasterError as exc:
            falhas.append(f'{empresa.nome}: {exc}')
    if ok:
        messages.success(request, f'{ok} empresa(s) atualizada(s) do Git.')
    for falha in falhas:
        messages.error(request, falha)
    if not ok and not falhas:
        messages.info(request, 'Nenhuma empresa com backup configurado.')
    return redirect('master_empresa', codigo=codigo) if codigo else redirect('master_home')


@master_required
@require_POST
def configurar_backup(request, codigo):
    empresa = _empresa_or_redirect(request, codigo)
    if empresa:
        try:
            master.configurar_repositorio(empresa)
            messages.success(request, 'Repositório privado criado e primeiro backup enviado.')
        except (MasterError, master.backup_remoto.BackupError) as exc:
            empresa.data['erro'] = str(exc)
            empresa.save()
            messages.error(request, str(exc))
    return redirect('master_empresa', codigo=codigo)


@master_required
@require_POST
def publicar(request, codigo):
    empresa = _empresa_or_redirect(request, codigo)
    if empresa:
        try:
            espelho.fechar(codigo)  # garante que nada está gravando no banco durante o envio
            master.publicar(empresa)
            messages.success(request, 'Banco da implantação enviado para o Git (criptografado).')
        except (MasterError, master.backup_remoto.BackupError) as exc:
            messages.error(request, str(exc))
    return redirect('master_empresa', codigo=codigo)


@master_required
@require_POST
def entrar(request, codigo):
    empresa = _empresa_or_redirect(request, codigo)
    if empresa is None:
        return redirect('master_home')
    try:
        url = espelho.abrir(empresa, request.build_absolute_uri(reverse('master_empresa', args=[codigo])))
    except MasterError as exc:
        messages.error(request, str(exc))
        return redirect('master_empresa', codigo=codigo)
    return redirect(url)


@master_required
@require_POST
def fechar(request, codigo):
    if espelho.fechar(codigo):
        messages.info(request, 'Empresa fechada.')
    return redirect('master_empresa', codigo=codigo)


@master_required
@require_POST
def restaurar(request, codigo):
    empresa = _empresa_or_redirect(request, codigo)
    if empresa:
        try:
            espelho.fechar(codigo)
            master.restaurar_ponto(empresa, request.POST.get('arquivo', ''))
            messages.success(request, f'Backup de {empresa.data["espelho_de"]} aberto. "Entrar" e o pacote usam esta cópia.')
        except (MasterError, master.backup_remoto.BackupError, master.cofre.CofreError) as exc:
            messages.error(request, str(exc))
    return redirect('master_empresa', codigo=codigo)


@master_required
@require_POST
def pacote(request, codigo):
    empresa = _empresa_or_redirect(request, codigo)
    if empresa is None:
        return redirect('master_home')
    try:
        espelho.fechar(codigo)
        path = master.gerar_pacote(empresa)
    except MasterError as exc:
        messages.error(request, str(exc))
        return redirect('master_empresa', codigo=codigo)
    return FileResponse(open(path, 'rb'), as_attachment=True, filename=path.name)
