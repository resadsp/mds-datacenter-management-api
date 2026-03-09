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

### 0.1) Komisija demo flow (12 koraka)

1. Uloguj se kao `admin1` i pokreni `POST /api/v1/seed` (dugme `Seed bazu` ili Swagger).
  - Očekivano: `200` i poruka `Baza je uspešno seedovana.` (ili `409` ako je već seedovano).
2. Prikaži `GET /api/v1/stats/`, `GET /api/v1/devices/` i `GET /api/v1/racks/`.
  - Očekivano: `200` i popunjeni podaci.
3. Kao `admin1` dodaj novi rack i novi uređaj.
  - Očekivano: uspešan unos i vidljivost u listama.
4. Dodeli novi uređaj u rack, pa ga zatim ukloni iz rack-a (`assign`/`unassign`).
  - Očekivano: status i opterećenje rack-a se ažuriraju bez greške.
5. Pokreni balansiranje (`Pokreni balansiranje`) i po potrebi primeni predlog.
  - Očekivano: predlog dodela bez kršenja `total_units` i `max_power`.
6. Odjavi se i uloguj kao `admin2`, pa izvrši izmenu nad postojećim uređajem ili rack-om.
  - Očekivano: izmena uspešna i audit beleži `actor_username=admin2`.
7. Odjavi se i uloguj kao `admin3`, pa uradi drugu izmenu (npr. opis ili kapacitet).
  - Očekivano: izmena uspešna i audit beleži `actor_username=admin3`.
8. U `Audit Logovi` pokaži hronologiju akcija za `admin1`, `admin2`, `admin3`.
  - Očekivano: jasna razlika ko je izvršio koju akciju (`actor_username`, `action`, `entity_type`, `entity_id`, `Audit ID`).
9. Test paralelne izmene istog entiteta (2 browsera/sesije):
  - Otvori dva različita browser-a (ili regular + incognito), uloguj npr. `admin1` i `admin2`, učitaj isti uređaj/rack.
  - Pošalji update sa istim početnim `version` iz obe sesije gotovo istovremeno.
  - Očekivano: jedan update prolazi (`200`), drugi dobija `409` (optimistic locking konflikt verzije).
10. Uloguj se kao `viewer` i pokaži da nema pristup operativnim akcijama (RBAC).
  - Očekivano: viewer ne vidi operativna dugmad i dobija `403` na zabranjene akcije.
11. Uloguj se kao `operator` i pokaži da ima operativne akcije, ali ne i admin-only deo.
  - Očekivano: operator može CRUD/assign/balance, ali nema admin kontrole.
12. Kao admin testiraj odjavu kroz modal (`Odjavi se sa ovog uređaja` i `Odjavi se sa svih uređaja`).
  - Očekivano: obe putanje rade ispravno i sesije se ponašaju očekivano.

### 0.2) Komisija detaljni checklist (sve funkcionalnosti)

Preporuka: glavni demo radi kroz dashboard (`/dashboard`), a Swagger (`/docs`) koristi samo za tehničke provere koje UI ne izlaže direktno.

1. **Pokretanje i dostupnost servisa**
  - Pokreni `docker compose up -d --build`.
  - Otvori `/dashboard`, `/health`, `/health/live`, `/health/ready`, `/metrics`.

2. **Login i role kontekst**
  - U dashboard login formi uloguj se kao `admin1/admin123`.
  - Potvrdi da vidiš admin deo (`Audit Logovi`, admin kontrole).

3. **Seed kroz UI**
  - Klikni `Seed bazu`.
  - Očekivano: `200` poruka uspeha ili `409` ako je već seedovano (validan fallback).

4. **Stats i osnovni pregled sistema**
  - Proveri stat kartice (broj uređaja/rack-ova, snaga, iskorišćenost).
  - Osveži podatke i potvrdi da se dashboard puni bez greške.

5. **Devices CRUD + validacije**
  - Dodaj novi uređaj.
  - Probaj dupli `serial_number` i potvrdi grešku (`400`).
  - Izmeni uređaj i potvrdi uspeh.

6. **Racks CRUD + validacije**
  - Dodaj novi rack.
  - Probaj dupli `serial_number` i potvrdi grešku (`400`).
  - Izmeni rack i potvrdi uspeh.

7. **Assign/unassign + kapacitet**
  - Dodeli uređaj rack-u (validan slučaj).
  - Probaj dodelu koja prelazi `total_units` ili `max_power` i potvrdi odbijanje (`400`).
  - Ukloni dodelu (`unassign`) i potvrdi povratak uređaja u slobodan status.

8. **Soft delete + restore (UI)**
  - Arhiviraj uređaj i rack.
  - Uključi filter za arhivirane i potvrdi da se vide.
  - Vrati arhivirane entitete (`restore`) i potvrdi aktivan status.

9. **Balancing (UI)**
  - Pokreni balansiranje.
  - Pregledaj predlog i po potrebi primeni ga.
  - Potvrdi da predlog ne krši kapacitete rack-ova.

10. **RBAC dokaz (viewer/operator/admin)**
  - Odjavi se, prijavi kao `viewer` i potvrdi da su operativna dugmad skrivena/neaktivna.
  - Potvrdi da viewer nema pristup operativnim akcijama (403 na zabranjene akcije).
  - Prijavi se kao `operator` i potvrdi operativne akcije bez admin-only dela.

11. **Logout modal i session tok (UI)**
  - Klikni `Odjava` i potvrdi tri dugmeta u modalu (`Otkaži`, `Odjavi se sa ovog uređaja`, `Odjavi se sa svih uređaja`).
  - Testiraj obe odjave i potvrdi očekivano ponašanje sesije.

12. **Audit dokaz odgovornosti (UI)**
  - Otvori `Audit Logovi` kao admin.
  - Potvrdi da se vide `actor_username`, akcija i entitet (`entity_type`, `entity_id`).
  - Prikaži da se jasno razlikuju `Audit ID` i `entity_id`.

13. **Swagger-only tehničke provere (najsitniji detalji)**
  - `POST /api/v1/auth/refresh`: potvrda rotacije refresh tokena.
  - `POST /api/v1/auth/logout-all`: potvrda opoziva svih sesija korisnika.
  - `POST /api/v1/devices/{id}/assign/{rack_id}` sa `Idempotency-Key`: isti zahtev ne pravi dupli efekat.
  - Paralelni update istog uređaja sa istim `version`: očekivano `200` + `409` (optimistic locking).
  - `POST /api/v1/auth/tokens/cleanup` i `POST /api/v1/auth/users` (admin-only tehničke rute).

14. **Automatska verifikacija**
  - Pokreni `pytest -q`.
  - Za konkurentnost i edge-case tokove proveri posebno `tests/test_api_integration.py`.

### 0.3) Dokazna mapa (šta tačno dokazujete komisiji)

- **Auth lifecycle:** `login` → `refresh` → `logout/logout-all`.
- **RBAC:** `viewer` read-only, `operator/admin` operativne akcije.
- **Integritet domena:** kapacitet (`total_units`, `max_power`) pri assign/update.
- **Konkurentnost:** optimistic locking preko `version` (`409` na stale update).
- **Otpornost na retry:** `Idempotency-Key` na assign.
- **Sledljivost:** audit log ko/šta/kada/nad čim.
- **Operativna spremnost:** `/health`, `/health/live`, `/health/ready`, `/metrics`.

### 0.4) Dashboard-first, Swagger-second (preporuka za odbranu)

- **Dashboard-first:** koristi dashboard za glavni narativ i većinu funkcionalnosti (najjasnije za komisiju).
- **Swagger-second:** koristi Swagger samo za tehničke edge-case provere koje nisu praktične kroz UI.
- **Bez `curl` obaveze:** `curl` ostaje opcioni alat; nije potreban za standardnu komisijsku demonstraciju.

Fallback (ako seed vrati `409`):

- Poruka `Baza je već seedovana.` je očekivana ako podaci već postoje.
- U demou samo nastavi na korak 2 (stats/devices/racks), bez ponovnog seed-a.
- Ako želiš čist reset, pokreni `docker compose down -v` pa `docker compose up --build` i zatim seed ponovo.

Podrazumevani korisnici (za demo):

- `admin1` / `admin123`
- `admin2` / `admin123`
- `admin3` / `admin123`
- `operator` / `operator123`
- `viewer` / `viewer123`

Seed nije obavezan za pokretanje API-ja, ali je **preporučen** zbog demo podataka
(baza `datacenter.db` je u `.gitignore` i može biti prazna).

Za komisiju se preporučuje da odmah nakon podizanja API-ja pokrene seed
(`POST /api/v1/seed`) kako bi svi endpoint-i imali podatke za demonstraciju.

Seed endpoint je zaštićen (admin rola).
Za dashboard-first demo koristi dugme `Seed bazu`, a za API demonstraciju koristi Swagger:

- otvoriti `http://localhost:8000/docs`
- pokrenuti `POST /api/v1/seed` (**Try it out** → **Execute**)

Detaljni primeri za seed i API tokove su niže u sekcijama `5) Seed podaci` i `9) API rute`.

Provera da sve radi:

- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Liveness: `http://localhost:8000/health/live`
- Readiness: `http://localhost:8000/health/ready`
- Metrics (Prometheus): `http://localhost:8000/metrics`

Gašenje:

```bash
docker compose down
```

Napomena za bazu u Docker režimu:

- SQLite baza se čuva na Docker volume-u (`mds_data`) i ostaje sačuvana nakon `docker compose down` i ponovnog `up`.
- Baza se briše samo ako eksplicitno ukloniš volume, npr. `docker compose down -v`.

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
- Dockerized deployment za lako testiranje.
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

Ako koristiš PostgreSQL, postavi `DATABASE_URL` pre migracije (npr. kroz `.env` ili shell).

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

Napomena: `DEVICE_ID` i `RACK_ID` uzimaš iz JSON odgovora prethodnih `POST /api/v1/devices/` i `POST /api/v1/racks/` poziva (polje `id`).
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

1. Pokreni Docker Desktop i sačekaj status **Engine running**.
2. U Docker Desktop podešavanjima proveri da je uključeno **Use the WSL 2 based engine**.
3. U terminalu proveri i prebaci context na Linux engine:

  ```bash
  docker context ls
  docker context use desktop-linux
  docker version
  ```

4. Ako i dalje ne radi, resetuj WSL i Docker Desktop:

  ```powershell
  wsl --shutdown
  ```

  zatvori i ponovo pokreni Docker Desktop, pa probaj opet:

  ```bash
  docker compose up --build
  ```

Ako Docker Desktop ne može da startuje engine, uradi update WSL-a:

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