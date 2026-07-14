# SideKick Django

## Pokretanje lokalno

Instaliraj zavisnosti:

```bash
pip install -r requirements.txt
```

Primeni migracije baze:

```bash
python manage.py migrate
```

Ako želiš početne demo podatke i naloge:

```bash
python manage.py reseed_demo
```

Pokreni ASGI server:

```bash
python -m uvicorn sidekick.asgi:application --host 127.0.0.1 --port 8000
```

Ako koristiš Windows Python launcher:

```bash
py manage.py migrate
py manage.py reseed_demo
py -m uvicorn sidekick.asgi:application --host 127.0.0.1 --port 8000
```

Otvori aplikaciju u browseru:

```text
http://127.0.0.1:8000/
```
