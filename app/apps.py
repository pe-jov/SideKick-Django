# Autor: Luka Jankovic, 704/19
"""Konfiguracija Django aplikacije SideKick."""

from django.apps import AppConfig


class SidekickAppConfig(AppConfig):
    """Registruje osnovna podešavanja aplikacije SideKick u Django projektu."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

