# MDS Datacenter Management API

REST API aplikacija za upravljanje uređajima i rack-ovima u data centru, sa validacijama kapaciteta (units + snaga), praćenjem potrošnje i predlogom balansiranog rasporeda uređaja po rack-ovima.

---

## 0) Brzi start (komisija) — Docker

**Projekat je Dockerizovan i ovo je primarni način pokretanja za evaluaciju.**

```bash
git clone https://github.com/resadsp/mds-datacenter-management-api.git
cd mds-datacenter-management-api
docker compose up -d --build
```

API je dostupan na: `http://localhost:8000`
Swagger: `http://localhost:8000/docs`

Pregled sekcija za evaluaciju:

- `0.1` — glavni redosled demonstracije (standardni tok uživo).
- `0.2` — detaljni checklist za dodatna pitanja komisije.
- `0.5` — kratki plan za demonstraciju od približno 7 minuta.

### 0.1) Komisija — glavni demo flow

Dashboard je primarni kanal demonstracije. Swagger se koristi naknadno, samo za tehničke potvrde graničnih slučajeva.

1. Prijava kao `admin1` i pokretanje seed-a (dugme `Seed bazu`; alternativno Swagger).
  - Očekivano: `200` ili `409` ako je baza već seedovana.
2. Brzi pregled stanja sistema: stats, lista uređaja, lista rack-ova.
  - Očekivano: podaci su učitani i bez grešaka.
3. CRUD primer: kreirati jedan rack i jedan uređaj.
  - Očekivano: novi zapisi su vidljivi u listama.
4. `assign` pa `unassign` za uređaj.
  - Očekivano: status uređaja i opterećenje rack-a se menjaju ispravno.
5. Pokretanje balansiranja i pregled predloga.
  - Očekivano: nema kršenja `total_units` i `max_power`.
6. RBAC dokaz: prijava kao `viewer`, zatim kao `operator`.
  - Očekivano: `viewer` nema operativne akcije; `operator` ima operativne, bez admin-only dela.
7. Tok sesije: odjava sa trenutnog uređaja i odjava sa svih uređaja.
  - Očekivano: obe putanje rade i sesije se ponašaju očekivano.
8. Audit dokaz odgovornosti.
  - Očekivano: jasno se vide `actor_username`, `action`, `entity_type`, `entity_id` i `Audit ID`.

### 0.2) Komisija — detaljni checklist (po potrebi)

Ova sekcija služi kao rezerva kada komisija traži dublju proveru.

1. **Dostupnost servisa**
  - Pokrenuti `docker compose up -d --build`.
  - Proveriti `/dashboard`, `/health`, `/health/live`, `/health/ready`, `/metrics`.

2. **Login i role kontekst**
  - Prijava kao `admin1/admin123` i potvrda da su admin kontrole vidljive.

3. **Seed kroz UI**
  - Pokretanje akcije `Seed bazu`; očekivano `200` ili `409`.

4. **Stats i pregled sistema**
  - Provera kartica i osvežavanje podataka.

5. **Devices CRUD + validacije**
  - Kreiranje, izmena, test duplog `serial_number` (`400`).

6. **Racks CRUD + validacije**
  - Kreiranje, izmena, test duplog `serial_number` (`400`).

7. **Assign/unassign + kapacitet**
  - Validna dodela, zatim odbijanje kad se pređe `total_units` ili `max_power` (`400`), pa `unassign`.

8. **Soft delete + restore**
  - Arhiviranje, prikaz arhiviranih i vraćanje entiteta.

9. **Balancing**
  - Pokretanje, pregled i (po potrebi) primena predloga.

10. **RBAC provera**
  - `viewer`: bez operativnih akcija / `403` na zabranjene rute.
  - `operator`: operativne akcije bez admin-only dela.

11. **Logout modal i session tok**
  - Provera oba dugmeta odjave i očekivanog ponašanja sesije.

12. **Audit logovi**
  - Provera `actor_username`, `action`, `entity_type`, `entity_id`, `Audit ID`.

13. **Swagger tehničke provere (posle dashboard dela)**
  - `POST /api/v1/auth/refresh`.
  - `POST /api/v1/auth/logout-all`.
  - `POST /api/v1/devices/{id}/assign/{rack_id}` sa `Idempotency-Key`.
  - Paralelni update istog uređaja sa istim `version` (`200 + 409`).
  - `POST /api/v1/auth/tokens/cleanup` i `POST /api/v1/auth/users` (admin-only).

14. **Automatska verifikacija**
  - `pytest -q`.
  - Po potrebi i `tests/test_api_integration.py`.

### 0.3) Ključni kriterijumi evaluacije

- **Auth/session tok:** `login` → `refresh` → `logout/logout-all`.
- **RBAC pravila:** jasna razlika između `viewer`, `operator` i `admin`.
- **Integritet domena:** kapaciteti (`total_units`, `max_power`) se poštuju pri dodeli.
- **Konkurentnost:** optimistic locking preko `version` (`409` na stale update).
- **Otpornost na retry:** `Idempotency-Key` sprečava duple efekte.
- **Sledljivost:** audit log beleži ko je uradio šta i nad čim.
- **Operativna spremnost:** `/health`, `/health/live`, `/health/ready`, `/metrics`.

### 0.4) Redosled demonstracije

- Prvo dashboard (`/dashboard`) za kompletan tok rada.
- Posle Swagger (`/docs`) samo za tehničke detalje koji nisu praktični kroz UI.

### 0.5) Kratki demo plan (7 minuta)

1. Start: `docker compose up -d --build` + provera `/health`.
2. Login/RBAC: `admin1` pa `viewer` (pokazati ograničenja).
3. Osnovni tok: kreiranje rack-a i uređaja, `assign` + `unassign`.
4. Pouzdanost: `soft delete/restore` + optimistic locking (`200 + 409`).
5. Sesije: obe opcije odjave iz modala.
6. Audit: prikaz `actor_username`, `action`, `entity_id`, `Audit ID`.
7. Swagger završna tehnička potvrda: `racks`, `refresh`, `logout-all`.

### 0.6) Brze napomene za demo

- Ako seed vrati `409`, to znači da su podaci već prisutni; demonstracija se nastavlja bez reseta.
- Za čist reset koristi se `docker compose down -v`, pa ponovo `docker compose up --build`.
- Podrazumevani korisnici: `admin1/admin123`, `admin2/admin123`, `admin3/admin123`, `operator/operator123`, `viewer/viewer123`.
- Seed je zaštićen admin rolom i može kroz dugme `Seed bazu` ili kroz Swagger.
- SQLite se čuva u Docker volume-u `mds_data`; briše se samo sa `down -v`.

---

## 1) Kratak opis

Projekat implementira backend funkcionalnosti tražene zadatkom:

Uz backend zahteve, dashboard je UX/UI dorađen da demonstracija bude jasnija i brža za evaluatore.

- CRUD za entitete **Device** i **Rack**
- Dodela uređaja rack-u uz pravila:
  - uređaj zauzima `units_occupied` jedinica,
  - ne sme se preći kapacitet rack-a (`total_units`),
  - ne sme se preći maksimalna deklarisana snaga (`max_power`)
- Rack detalji prikazuju i:
  - trenutnu ukupnu potrošnju (`current_power`)
  - trenutno zauzeće jedinica (`current_units`)
- Predlog rasporeda uređaja po rack-ovima (`/api/v1/balance/`) sa ciljem ujednačenije procentualne iskorišćenosti snage rack-ova.
  - Balansiranje mogu da pokrenu samo role `operator` i `admin`.
- Swagger/OpenAPI dokumentacija.
- Docker deployment za lako testiranje.
- Refresh token flow (access + refresh, rotacija refresh tokena).
- Global `X-Request-ID`, structured JSON logging, osnovni rate limiting i secure response header-i.
- Liveness/readiness endpoint-i za produkciono health praćenje.
- Prometheus metrike (`/metrics`) za broj zahteva, latenciju i rate-limit blokade.
- Admin audit log endpoint sa paginacijom/sort/filter podrškom i dashboard prikazom.
- Dashboard UX/UI je dodatno unapređen za demonstraciju (jasniji tok rada, role-aware kontrole, konzistentne akcije i odjava modal).
- `DATABASE_URL` podrška (SQLite ili PostgreSQL kroz env konfiguraciju).
- Standardizovan error odgovor (`detail`, `code`, `request_id`, opcioni `errors`).

> Napomena: implementirana je osnovna JWT autentikacija i RBAC autorizacija.
> Napomena: UI nije obavezan po zadatku; aplikacija je namenjena korišćenju preko REST API poziva.

---

## 1.1) Usklađenost sa zadatkom (sažeto)

- Implementirani su entiteti `Device` i `Rack` sa traženim poljima i validacijama.
- Omogućene su CRUD operacije nad oba entiteta.
- Dodela uređaja rack-u je implementirana preko posebnog endpoint-a, uz proveru `total_units` i `max_power`.
- Pri dohvatanju rack-a vraćaju se i trenutna potrošnja (`current_power`) i zauzeće (`current_units`).
- Implementiran je endpoint za predlog balansiranog rasporeda (`/api/v1/balance/`) uz pretpostavku praznih rack-ova (predlog rasporeda).
- Unit testovi su pokriveni za funkcionalnost balansiranja (`tests/test_balancing.py`).

---

## 2) Tehnologije

- Python
- FastAPI
- SQLAlchemy
- SQLite (`datacenter.db`)
- PostgreSQL (opciono preko `DATABASE_URL`)
- Pytest
- Docker / Docker Compose

---

## 2.1) Env konfiguracija

- `DATABASE_URL` (default: `sqlite:///./datacenter.db`)
- `CORS_ALLOWED_ORIGINS` (default: `*`, CSV lista)
- `RATE_LIMIT_MAX_REQUESTS` (default: `120`)
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `MAX_REQUEST_SIZE_BYTES` (default: `2097152`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: `60`)
- `REFRESH_TOKEN_EXPIRE_DAYS` (default: `7`)
- `REDIS_URL` (default u docker compose: `redis://redis:6379/0`)
- `STATS_CACHE_TTL_SECONDS` (default: `30`)
- `ASSIGN_IDEMPOTENCY_TTL_SECONDS` (default: `600`)

Napomena:

- `.env` fajl nije obavezan i nije verzionisan u repozitorijumu.
- Konfiguracija se može zadati preko sistemskih env varijabli ili lokalnog `.env` fajla.

---

## 3) Struktura projekta (bitno za evaluaciju)

- `app/main.py` — FastAPI app i dashboard
- `app/auth.py` — JWT, RBAC helperi i bootstrap podrazumevanih korisnika
- `app/audit.py` — pomoćne funkcije za audit upis
- `app/middleware.py` — request-id, logging, security headeri, rate limit, metrics
- `app/models.py` — SQLAlchemy modeli
- `app/schemas.py` — Pydantic šeme
- `app/balancing.py` — algoritam balansiranja
- `app/routers/`:
  - `auth.py`
  - `devices.py`
  - `racks.py`
  - `balancing.py`
  - `stats.py`
  - `seed.py` (**API seed endpoint**)
  - `audit_logs.py`
- `tests/test_balancing.py` — testovi balansiranja
- `tests/test_api_integration.py` — integracioni testovi API tokova
- `seed.py` (root) — **CLI seed skripta** (`python seed.py`)
- `alembic/` — migracije baze
- `alembic.ini` — Alembic konfiguracija
- `.github/workflows/ci.yml` — CI pipeline (lint/test/security/build/smoke)
- `static/` — statički resursi dashboard-a
- `Dockerfile`
- `docker-compose.yml`

---

## 4) Pokretanje aplikacije (Docker — primarno za evaluaciju)

### Opcija A: Docker Compose

```bash
docker compose up --build
```

Aplikacija:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Gašenje:

```bash
docker compose down
```

### Opcija B: samo Dockerfile

```bash
docker build -t mds-datacenter-api .
docker run --rm -p 8000:8000 mds-datacenter-api
```

---

## 5) Seed podaci (2 načina)

Baza `datacenter.db` je u `.gitignore`, pa su obezbeđena **dva načina** za seed:

### A) CLI seed (root fajl)

```bash
python seed.py
```

### B) API seed endpoint

```bash
# Seed endpoint zahteva admin autentikaciju
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"admin123"}' | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/api/v1/seed \
  -H "Authorization: Bearer $TOKEN"
```

> Seed je namenjen brzom punjenju test podacima za komisiju.
> Ako je baza već seedovana, API seed endpoint vraća `409 Baza je već seedovana`.

---

## 6) Lokalno pokretanje (bez Docker-a)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
./run.sh
```

Alternativno:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 7) Testovi

Pokretanje svih testova:

```bash
pytest -q
```

Pokretanje samo balansiranja:

```bash
pytest -v tests/test_balancing.py
```

Pokretanje integracionih testova API tokova:

```bash
pytest -v tests/test_api_integration.py
```

---

## 8) Operativni endpoint-i i error format

- `GET /health` — osnovni health check.
- `GET /health/live` — liveness check (proces je živ).
- `GET /health/ready` — readiness check (DB + Redis kada je podešen `REDIS_URL`).
- `GET /metrics` — Prometheus metrike (request count, duration, rate-limit blocked).

Dodatno uvedeno:

- `assign` operacija podržava `Idempotency-Key` header (ponovljeni isti zahtev vraća isti uspešan rezultat).
- `/stats/` je keširan u kratkom TTL prozoru i keš se invalidira na mutacije uređaja/rack-ova i seed operaciju.

Primer standardizovanog error odgovora:

```json
{
  "detail": "Validation failed",
  "code": "validation_error",
  "request_id": "a1b2c3...",
  "errors": [
    {
      "loc": ["body", "name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## 9) API rute

### Devices

- `POST /api/v1/devices/`
- `GET /api/v1/devices/?page=1&page_size=20&sort_by=id&sort_order=asc&name=&serial_number=&rack_id=&include_deleted=`
- `GET /api/v1/devices/{device_id}`
- `PUT /api/v1/devices/{device_id}`
- `DELETE /api/v1/devices/{device_id}`
- `POST /api/v1/devices/{device_id}/restore`
- `POST /api/v1/devices/{device_id}/assign/{rack_id}`
- `POST /api/v1/devices/{device_id}/unassign`

### Racks

- `POST /api/v1/racks/`
- `GET /api/v1/racks/?page=1&page_size=20&sort_by=id&sort_order=asc&name=&serial_number=&include_deleted=`
- `GET /api/v1/racks/{rack_id}`
- `PUT /api/v1/racks/{rack_id}`
- `DELETE /api/v1/racks/{rack_id}`
- `POST /api/v1/racks/{rack_id}/restore`

### Balancing

- `POST /api/v1/balance/`
  - dozvoljene role: `operator`, `admin`

### Stats

- `GET /api/v1/stats/`

### Seed

- `POST /api/v1/seed`

### Auth

- `POST /api/v1/auth/token`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all`
- `POST /api/v1/auth/tokens/cleanup` (admin)
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/users` (admin)

Auth/sesije (sažeto za komisiju):

- `login` vraća `access_token` (kratko-živeći) i `refresh_token` (duže-živeći).
- `refresh` rotira refresh token (izdaje novi, stari postaje nevažeći).
- `logout` opoziva samo trenutnu sesiju (jedan refresh token).
- `logout-all` opoziva sve aktivne sesije istog korisnika.

Brza verifikacija (Swagger):

1. `POST /api/v1/auth/login` → sačuvaj `access_token` i `refresh_token`.
2. `POST /api/v1/auth/refresh` sa starim refresh tokenom → dobijaš novi token par.
3. `POST /api/v1/auth/logout` sa novim refresh tokenom → ta sesija je ugašena.
4. `POST /api/v1/auth/logout-all` (dok si ulogovan) → sve sesije korisnika postaju nevažeće.
5. Ponovni `refresh` sa opozvanim tokenom treba da vrati `401`.

Napomena za demo kroz Swagger:

- Primarni (bezbedniji) način je `Authorization: Bearer` preko `Authorize` dugmeta.
- U demo režimu podržan je i `access_token` query param za lakše testiranje po rutama.

Napomena za dashboard odjavu:

- Dugme `Odjava` otvara modal sa dve opcije odjave:
  - `Odjavi se sa ovog uređaja` → poziva `POST /api/v1/auth/logout` (revokuje samo trenutni refresh token/sesiju).
  - `Odjavi se sa svih uređaja` → poziva `POST /api/v1/auth/logout-all` (revokuje sve aktivne sesije istog korisnika).
  - Modal sadrži i `Otkaži` dugme.
  - UI napomena: sva dugmad u odjavnom modalu su prikazana konzistentno (ista boja i širina, u jednoj koloni).

### Audit Logs

- `GET /api/v1/audit-logs/?page=1&page_size=20&sort_by=created_at&sort_order=desc&action=&entity_type=&actor_username=` (admin)

Primeri (praćenje koji admin je radio izmene):

```bash
# Svi audit logovi, najnoviji prvo (po vremenu)
curl "http://localhost:8000/api/v1/audit-logs/?page=1&page_size=20&sort_by=created_at&sort_order=desc"

# Samo logovi za jednog admina/operatora (npr. admin1)
curl "http://localhost:8000/api/v1/audit-logs/?page=1&page_size=20&actor_username=admin1&sort_by=created_at&sort_order=desc"

# Stabilan redosled po ID-u zapisa (najnoviji zapis prvo)
curl "http://localhost:8000/api/v1/audit-logs/?page=1&page_size=20&sort_by=id&sort_order=desc"

# Samo izmene uređaja od konkretnog admina
curl "http://localhost:8000/api/v1/audit-logs/?page=1&page_size=20&entity_type=device&actor_username=admin1&sort_by=created_at&sort_order=desc"
```

Napomena:

- `actor_username` = ko je izvršio akciju (admin/operator korisničko ime).
- `entity_type` + `entity_id` = nad čim je akcija izvršena (npr. `device` ID 12).
- `id` je ID audit zapisa (primarni ključ) i koristan je za stabilno sortiranje/referenciranje.

Detaljni request/response modeli su u Swagger dokumentaciji (`/docs`).

---

## 10) CI pipeline

GitHub Actions workflow je dodat u `.github/workflows/ci.yml` i radi:

- lint (`ruff check .`)
- testove (`pytest -q`)
- security scan (`bandit -r app -q`)
- Docker build
- smoke test (`/health`)

---

## 11) Alembic migracije

Inicijalna Alembic konfiguracija i početna migracija su dodate.

- inicijalizacija je u `alembic.ini` i `alembic/env.py`
- početna migracija: `alembic/versions/20260302_0001_initial_schema.py`

Primer pokretanja:

```bash
alembic upgrade head
```

Ako se koristi PostgreSQL, potrebno je postaviti `DATABASE_URL` pre migracije (npr. kroz `.env` ili shell).

---

## 12) Rate limiting

- Middleware prvo koristi Redis token-bucket limiter (ako je `REDIS_URL` dostupan).
- Ako Redis nije dostupan, automatski pada na in-memory limiter.
- Prekoračenje limita vraća `429 Too Many Requests`.

---

## 13) API integracioni testovi

Dodata je kratka integraciona pokrivenost za:

- auth refresh rotaciju i revokaciju/logout tok
- standardizovan pagination envelope (`items` + `meta`) za devices i racks

Konkretno za konkurentne izmene (optimistic locking), pokriven je scenario
u kom dva paralelna update zahteva nad istim uređajem daju tačno jedan uspeh i jedan konflikt (`200` + `409`).

Test fajl: `tests/test_api_integration.py`.

---

## 14) Kako se uređaj dodeljuje rack-u (primer)

Ako već postoje rack i uređaj, dodela se radi jednim pozivom:

- `POST /api/v1/devices/{device_id}/assign/{rack_id}`

Praktični tok (od prazne baze) je 3 koraka:

1. kreiraj rack (`POST /api/v1/racks/`)
2. kreiraj uređaj (`POST /api/v1/devices/`)
3. dodeli uređaj rack-u (`POST /api/v1/devices/{device_id}/assign/{rack_id}`)

Primer:

```bash
# 1) Kreiraj rack
curl -X POST http://localhost:8000/api/v1/racks/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Rack A3",
    "description": "Glavni rack",
    "serial_number": "RACK-A3-003",
    "total_units": 42,
    "max_power": 10000
  }'

# 2) Kreiraj uređaj
curl -X POST http://localhost:8000/api/v1/devices/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Server Dell R740",
    "description": "DB server",
    "serial_number": "DEV-R740-001",
    "units_occupied": 2,
    "power_consumption": 450
  }'

# 3) Dodeli uređaj rack-u (zameni PLACEHOLDER vrednosti stvarnim ID-jevima)
curl -X POST http://localhost:8000/api/v1/devices/{DEVICE_ID}/assign/{RACK_ID}
```

Napomena: primeri iznad su pisani za `bash` (Linux/macOS). Na Windows CMD/PowerShell sintaksa za varijable i navodnike može da se razlikuje.

Windows (PowerShell) primer sa jedinstvenim serijskim brojevima:

```powershell
$R = Get-Date -UFormat %s

curl.exe -X POST http://localhost:8000/api/v1/racks/ -H "Content-Type: application/json" -d "{\"name\":\"Rack A1\",\"description\":\"Glavni rack\",\"serial_number\":\"RACK-A1-$R\",\"total_units\":42,\"max_power\":10000}"

curl.exe -X POST http://localhost:8000/api/v1/devices/ -H "Content-Type: application/json" -d "{\"name\":\"Server Dell R740\",\"description\":\"DB server\",\"serial_number\":\"DEV-R740-$R\",\"units_occupied\":2,\"power_consumption\":450}"
```

Ako je uređaj već dodeljen ili rack nema dovoljno kapaciteta (`total_units` / `max_power`), API vraća `400`.

Napomena: `DEVICE_ID` i `RACK_ID` se uzimaju iz JSON odgovora prethodnih `POST /api/v1/devices/` i `POST /api/v1/racks/` poziva (polje `id`).
Napomena: `serial_number` za `Device` i `Rack` mora biti jedinstven; za duplikat API vraća `400`.

---

## 15) Balancing logika (sažeto)

Endpoint prima listu uređaja i rack-ova i vraća:

- dodeljene parove `device_id -> rack_id`
- listu nedodeljenih uređaja (ako nema kapaciteta)

Pri predlogu se vodi računa o:

- `total_units` kapacitetu rack-a
- `max_power` kapacitetu rack-a
- cilju što ujednačenijeg procentualnog opterećenja snage rack-ova

Napomena: balansiranje ne uzima u obzir trenutni raspored u bazi i ne određuje tačne U pozicije uređaja, već daje predlog rasporeda po rack-ovima na nivou kapaciteta.

Output je **predlog rasporeda**.

---

## 16) Screenshot dashboard-a

Dashboard je dodatna pomoćna vizualizacija; primarni način upotrebe i evaluacije je kroz REST API (`/docs`, `curl`, Postman).

![Početna strana](docs/images/pozadina_projekta.png)

---

## 17) Troubleshooting

Ako `docker compose up` prijavi `port 8000 already allocated`:

- ugasiti proces/kontejner koji koristi 8000, ili
- promeniti mapiranje porta u `docker-compose.yml` na npr. `8001:8000`, pa koristiti `http://localhost:8001/docs`.

Ako na Windows-u dobiješ grešku:

`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`

to znači da Docker Desktop Linux engine nije pokrenut ili nije izabran pravi Docker context.

Koraci:

1. Pokrenuti Docker Desktop i sačekati status **Engine running**.
2. U Docker Desktop podešavanjima proveriti da je uključeno **Use the WSL 2 based engine**.
3. U terminalu proveriti i prebaciti context na Linux engine:

  ```bash
  docker context ls
  docker context use desktop-linux
  docker version
  ```

4. Ako i dalje ne radi, resetovati WSL i Docker Desktop:

  ```powershell
  wsl --shutdown
  ```

  zatvoriti i ponovo pokrenuti Docker Desktop, pa pokušati ponovo:

  ```bash
  docker compose up --build
  ```

Ako Docker Desktop ne može da startuje engine, uraditi update WSL-a:

```powershell
wsl --update
```

---

## 18) Verzija

- API verzija: `1.0.0`
- Datum finalne pripreme: 24.02.2026.

---

## 19) Rečnik pojmova (za komisiju)

- `access token` — kratko-živeći JWT za pristup zaštićenim API rutama.
- `refresh token` — duže-živeći token kojim se izdaje novi access token bez ponovne prijave.
- `revoke (opoziv tokena)` — token se server-side označi kao nevažeći i više se ne prihvata.
- `logout` — odjava trenutne sesije (jedan refresh token).
- `logout-all` — odjava svih aktivnih sesija istog korisnika (svi refresh tokeni korisnika).
- `RBAC` — kontrola pristupa po rolama (`admin`, `operator`, `viewer`).
- `soft delete` — logičko arhiviranje (`deleted_at`) umesto fizičkog brisanja iz baze.
- `restore` — vraćanje arhiviranog entiteta u aktivno stanje.
- `optimistic locking` — zaštita konkurentnih izmena preko `version` polja (stale update vraća `409`).
- `idempotency key` — ponovljeni isti zahtev daje isti ishod bez duplih efekata.
- `seed` — kontrolisano inicijalno punjenje baze demo podacima.
- `heurističko balansiranje` — praktična optimizacija rasporeda uz poštovanje ograničenja, bez garancije globalnog optimuma.