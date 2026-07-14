# Autor: Luka Jankovic, 704/19
"""WSGI ulazna tačka za pokretanje SideKick Django aplikacije."""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sidekick.settings")

application = get_wsgi_application()

