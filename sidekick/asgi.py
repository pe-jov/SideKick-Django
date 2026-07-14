"""ASGI ulazna tačka za pokretanje SideKick Django aplikacije."""

# Author Petar Jovanovic
import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application
import socketio


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sidekick.settings")

django_asgi_app = get_asgi_application()
if settings.DEBUG:
    django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

from app.realtime import sio


application = socketio.ASGIApp(sio, django_asgi_app)
