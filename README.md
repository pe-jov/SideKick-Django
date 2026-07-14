# SideKick Django

## Pokretanje lokalno

Napomena za macOS:

- Ako komanda `python` ne postoji na sistemu, koristi `python3`.
- Isto važi i za `pip`, odnosno koristi `python3 -m pip`.

Instaliraj zavisnosti:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
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

## Pokretanje običnih testova

Za pokretanje svih standardnih Django testova:

```bash
source .venv/bin/activate
python manage.py test
```

Ako želiš da pustiš samo određeni test fajl:

```bash
python manage.py test app.tests.test_context_helpers
```

## Pokretanje Selenium testova

Selenium testovi koriste Chrome i Django live test server.

Pokretanje Selenium testova:

```bash
source .venv/bin/activate
SELENIUM_BROWSER=chrome python manage.py test app.tests.test_selenium_webdriver
```

Ako želiš da vidiš browser prozor umesto headless režima:

```bash
SELENIUM_HEADLESS=0 SELENIUM_BROWSER=chrome python manage.py test app.tests.test_selenium_webdriver
```

Podrazumevano se koristi Chrome binarka sa macOS putanje:

```text
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

Ako ti je Chrome na drugoj lokaciji, postavi:

```bash
SELENIUM_BROWSER=firefox python manage.py test app.tests.test_selenium_webdriver
```

Napomena:

- Selenium testovi će biti preskočeni ako browser driver nije dostupan.
- U nekim sandbox ili CI okruženjima live server možda ne može da se podigne, pa će test takođe biti preskočen umesto da padne.
