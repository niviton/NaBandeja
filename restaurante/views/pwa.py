from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.cache import cache_control


@cache_control(max_age=3600)
def pwa_manifest(request):
    return render(request, 'pwa/manifest.webmanifest', content_type='application/manifest+json')


@cache_control(no_cache=True)
def pwa_service_worker(request):
    return render(request, 'pwa/sw.js', content_type='application/javascript')


def download_ca_cert(request):
    cert_path = settings.DATA_DIR / 'certs' / 'rootCA.pem'
    if not cert_path.exists():
        raise Http404
    return FileResponse(open(cert_path, 'rb'), as_attachment=True, filename='nabandeja-rootCA.pem',
                        content_type='application/x-pem-file')
