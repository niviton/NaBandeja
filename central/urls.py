"""Endereços sem loja (modo várias lojas): login geral e painel central."""

from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve

from restaurante.views import pwa

from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('sair/', views.logout_view, name='logout'),
    path('central/', views.home, name='central_home'),
    path('central/nova/', views.new_store, name='central_new'),
    path('central/<slug:code>/entrar/', views.enter_store, name='central_enter'),
    path('central/<slug:code>/ativar/', views.toggle_store, name='central_toggle'),
    path('manifest.webmanifest', pwa.pwa_manifest, name='pwa_manifest'),
    path('sw.js', pwa.pwa_service_worker, name='pwa_service_worker'),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
