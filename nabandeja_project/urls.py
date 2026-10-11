from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    # Login com Google: só as rotas do provedor (sem cadastro/senha do allauth).
    path('accounts/', include('allauth.socialaccount.providers.google.urls')),
    path('accounts/social/', include('allauth.socialaccount.urls')),
    path('accounts/login/', RedirectView.as_view(pattern_name='login'), name='account_login'),
    path('', include('restaurante.urls')),
    # Uploads (logo, fotos). Servidos pelo próprio Django porque o sistema roda
    # na rede local, sem Nginx. Arquivos estáticos ficam com o WhiteNoise.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
