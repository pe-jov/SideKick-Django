# Autor: Luka Jankovic, 704/19
"""Glavna URL konfiguracija Django projekta SideKick."""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


# Registruje administratorske i aplikativne rute na nivou celog projekta.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

