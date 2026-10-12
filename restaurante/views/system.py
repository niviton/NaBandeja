"""Gerente: status do sistema, backup, licença e assistente de primeiro uso."""

import platform
import shutil
import sys
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..models import AppSettings, Category, Table
from ..permissions import manager_required
from ..services import backup, license
from ..services import tables as table_service
from ..services.audit import audit
from ..services.pix import KEY_TYPES, PixError, build_payload


def _disk_free_gb(path):
    try:
        return round(shutil.disk_usage(path).free / 1024 ** 3, 1)
    except OSError:
        return None


def _error_lines(limit=15):
    log_file = Path(settings.LOG_DIR) / 'nabandeja.log'
    if not log_file.exists():
        return []
    lines = log_file.read_text(encoding='utf-8', errors='replace').splitlines()
    return [line for line in lines if ' ERROR ' in line or ' CRITICAL ' in line][-limit:]


@manager_required
def system_status(request):
    store = AppSettings.get_settings()
    last_file, last_date = backup.last_backup()
    db_path = Path(settings.DATABASES['default']['NAME']) if backup.is_sqlite() else None
    port = request.get_port()
    scheme = 'https' if request.is_secure() else 'http'
    return render(request, 'restaurante/admin/system.html', {
        'version': settings.NABANDEJA_VERSION,
        'license': license.status(store.license_key),
        'last_backup': last_date,
        'last_backup_name': last_file.name if last_file else '',
        'db_size_mb': round(db_path.stat().st_size / 1024 ** 2, 1) if db_path and db_path.exists() else None,
        'disk_free_gb': _disk_free_gb(settings.DATA_DIR),
        'local_ip': settings.LOCAL_IP,
        'links': {
            'Este computador': f'{scheme}://localhost:{port}',
            'Celulares e tablets': f'{scheme}://{settings.LOCAL_IP or "IP-DO-PC"}:{port}',
        },
        'python': f'{platform.python_version()} ({sys.platform})',
        'realtime': settings.ENABLE_REALTIME and settings.HAS_CHANNELS,
        'errors': _error_lines(),
        'active_menu': 'system',
    })


@manager_required
@require_POST
def backup_now(request):
    path = backup.run_backup()
    if path:
        audit(request, 'backup.manual', f'Backup manual: {path.name}.')
        messages.success(request, f'Backup criado: {path.name}')
    else:
        messages.error(request, 'Backup automático só funciona com banco SQLite.')
    return redirect('system_status')


@manager_required
def backup_download(request):
    path, _ = backup.last_backup()
    if not path:
        raise Http404
    audit(request, 'backup.download', f'Backup baixado: {path.name}.')
    return FileResponse(open(path, 'rb'), as_attachment=True, filename=f'nabandeja_{path.name}')


# ------------------------------------------------------------------ assistente

class StoreStepForm(forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = ['store_name', 'slogan', 'logo', 'phone', 'city', 'primary_color']
        widgets = {'primary_color': forms.TextInput(attrs={'type': 'color'})}


class PixStepForm(forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = ['pix_key', 'pix_key_type', 'pix_name', 'pix_city']

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('pix_key'):
            try:
                build_payload(cleaned['pix_key'], cleaned.get('pix_name') or 'LOJA',
                              cleaned.get('pix_city') or self.instance.city or 'CIDADE',
                              amount='1', key_type=cleaned.get('pix_key_type') or 'auto')
            except PixError as exc:
                raise forms.ValidationError(str(exc))
        return cleaned


STEPS = ['loja', 'pix', 'mesas', 'cardapio']


@manager_required
def setup_wizard(request, step='loja'):
    if step not in STEPS:
        return redirect('setup_wizard', step='loja')
    store = AppSettings.get_settings()
    next_step = STEPS[STEPS.index(step) + 1] if step != STEPS[-1] else None
    form = None

    if step == 'loja':
        form = StoreStepForm(request.POST or None, request.FILES or None, instance=store)
    elif step == 'pix':
        form = PixStepForm(request.POST or None, instance=store)

    if request.method == 'POST':
        if form is not None:
            if form.is_valid():
                form.save()
                return redirect('setup_wizard', step=next_step)
        elif step == 'mesas':
            try:
                count = max(0, min(200, int(request.POST.get('count') or 0)))
            except ValueError:
                count = 0
            if count:
                table_service.create_tables(count)
            return redirect('setup_wizard', step=next_step)
        elif step == 'cardapio':
            names = [name.strip() for name in request.POST.get('categories', '').split(',') if name.strip()]
            for index, name in enumerate(names):
                Category.objects.get_or_create(name=name[:100], defaults={'order': index})
            store.setup_completed = True
            store.save(update_fields=['setup_completed'])
            messages.success(request, 'Tudo pronto! Agora cadastre os produtos do cardápio.')
            return redirect('admin_menu')

    return render(request, 'restaurante/admin/setup.html', {
        'step': step,
        'step_number': STEPS.index(step) + 1,
        'steps_total': len(STEPS),
        'step_names': ['Loja', 'PIX', 'Mesas', 'Cardápio'],
        'form': form,
        'key_types': KEY_TYPES,
        'tables_count': Table.objects.count(),
        'categories': Category.objects.all(),
    })


@manager_required
@require_POST
def setup_skip(request):
    store = AppSettings.get_settings()
    store.setup_completed = True
    store.save(update_fields=['setup_completed'])
    return redirect('admin_dashboard')
