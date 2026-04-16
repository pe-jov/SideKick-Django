# SideKick Django

Classic Django refactor of the SideKick React app.

## Run locally

```bash
pip install -r requirements.txt
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

The app is server-rendered with Django templates, static CSS, and small vanilla JavaScript for dark mode and the collaborators modal.

## Cloudflare Pages deployment

Do not deploy this project directly to Cloudflare Pages if you need the Django app to work.

Cloudflare Pages can run Python during the build step, but it does not provide a Python WSGI/ASGI runtime for serving Django requests. Pages deploys static files and JavaScript/Workers-based Functions. This project needs a running Django server, so a Pages deployment would only publish static output and routes like `/`, `/profile/`, and `/spaces/1/` would not be handled by Django.

If you still connect the repository to Cloudflare Pages as a static-files experiment, use these settings:

```text
Framework preset: None
Build command: pip install -r requirements.txt && python manage.py collectstatic --noinput
Build output directory: staticfiles
Root directory: /
Environment variable: PYTHON_VERSION=3.11.5
```

That setup is not a production deployment for this app. It only proves that static assets can be collected.

## Recommended Cloudflare setup

Use a Python-capable host for Django, then put Cloudflare in front of it:

1. Deploy Django to a Python host such as Render, Railway, Fly.io, PythonAnywhere, or a VPS.
2. Run the app with a production WSGI/ASGI server such as Gunicorn or Uvicorn.
3. Configure `ALLOWED_HOSTS` for the public domain.
4. Serve static files with WhiteNoise or object storage.
5. Point your domain through Cloudflare DNS, or use Cloudflare Tunnel to expose the Django server.

Cloudflare Pages is a good fit if the app is later converted to a static frontend. For the current Django-only version, use Cloudflare as DNS/proxy/tunnel, not as the Python application host.
