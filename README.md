# SideKick Django

## Pokretanje lokalno

Instaliraj zavisnosti:

```bash
pip install -r requirements.txt
```

Pokreni ASGI server:

```bash
python -m uvicorn sidekick.asgi:application --host 127.0.0.1 --port 8000
```

Ako koristiš Windows Python launcher:

```bash
py -m uvicorn sidekick.asgi:application --host 127.0.0.1 --port 8000
```

Otvori aplikaciju u browseru:

```text
http://127.0.0.1:8000/
```
