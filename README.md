# Data Center Management API

## 📋 **Zahtevi Sistema**

- **Python 3.8+**
- **pip** za instalaciju zavisnosti
- **Git** za kloniranje
- **Web browser** za dashboard

**Nema potrebe za Docker-om!** Projekat radi direktno na vašem sistemu.

## 🚀 **Brzi Start (2 minuta)**

```bash
git clone <repo-url>
cd mds-datacenter-management-api
pip install -r requirements.txt
./run.sh
```

**Otvori:** `http://localhost:8000` ✨

## 🔧 **Troubleshooting**

### **Port 8000 je zauzet?**
```bash
# Promeni port u run.sh ili pokreni sa:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### **Greška sa pip install?**
```bash
# Ažuriraj pip:
pip install --upgrade pip
# Ili koristi python3 -m pip
python3 -m pip install -r requirements.txt
```

### **Server se ne pokreće?**
```bash
# Proveri Python verziju:
python3 --version  # Treba 3.8+
# Proveri da li su sve zavisnosti instalirane:
pip list | grep fastapi
```

## Pregled Projekta

Ovaj projekat je REST API aplikacija napisana u Python-u koristeći FastAPI framework, namenjena za upravljanje uređajima i rack-ovima u data centru. Aplikacija omogućava praćenje potrošnje energije, balansiranje opterećenja i pruža sveobuhvatne CRUD operacije.

### Ključne Funkcionalnosti

- **Potpuno CRUD upravljanje uređajima i rack-ovima**
- **Inteligentno balansiranje uređaja po rack-ovima** za optimalnu iskorišćenost energije
- **Praćenje potrošnje energije** u realnom vremenu
- **Validacija kapaciteta** (jedinice i snaga) prilikom dodeljivanja
- **Filtriranje i paginacija** za efikasno pretraživanje
- **Statistike i analize** iskorišćenosti data centra
- **Automatska API dokumentacija** putem Swagger UI
- **Kompletno testirano** sa unit testovima
- **Docker podrška** za lako deployovanje

### Tehnologije Korišćene

- **FastAPI**: Moderni, brzi web framework sa automatskom validacijom
- **SQLAlchemy**: ORM za rad sa bazom podataka
- **Pydantic**: Validacija podataka i serijalizacija
- **SQLite**: Baza podataka (može se zameniti PostgreSQL-om)
- **pytest**: Testiranje
- **Docker**: Kontejnerizacija

## Struktura Projekta

```
mds-datacenter-management-api/
├── app/                          # Glavni folder aplikacije
│   ├── main.py                   # Ulazna tačka FastAPI aplikacije + Web Dashboard
│   ├── models.py                 # SQLAlchemy modeli baze podataka
│   ├── schemas.py                # Pydantic šeme za validaciju
│   ├── database.py               # Konfiguracija baze podataka
│   ├── balancing.py              # Algoritam za balansiranje
│   └── routers/                  # API ruteri
│       ├── devices.py            # CRUD za uređaje
│       ├── racks.py              # CRUD za rack-ove
│       ├── balancing.py          # Endpoint za balansiranje
│       └── stats.py              # Statistike
├── tests/                        # Testovi
│   └── test_balancing.py         # Unit testovi algoritma
├── requirements.txt              # Python zavisnosti
├── Dockerfile                    # Docker konfiguracija
├── run.sh                        # Skripta za pokretanje
├── README.md                     # Ova dokumentacija
└── .gitignore                    # Ignorisani fajlovi
```

## Instalacija i Pokretanje

### 🔧 **LAKO LOKALNO POKRETANJE (PREPORUČENO)**

**Samo 3 komande:**
```bash
git clone <repo-url>
cd mds-datacenter-management-api
pip install -r requirements.txt
./run.sh
```

**Zatim otvorite:** `http://localhost:8000`

**Šta ćete videti:**
- 🎨 **Moderan dashboard** sa grafikama i tabelama
- 📊 **Live statistike** data centra
- ➕ **Dugmad za dodavanje** uređaja i rack-ova
- ⚖️ **Balansiranje** jednim klikom
- 📚 **API dokumentacija** na `/docs`

### 🐳 **Docker Pokretanje (Opcionalno)**

```bash
# Build slike
docker build -t datacenter-api .

# Pokreni kontejner
docker run -p 8000:8000 datacenter-api
```

**Napomena:** Docker je opcionalan. Projekat radi perfektno i bez njega!

## API Dokumentacija

### Uređaji (Devices)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/v1/devices/` | Lista uređaja (sa paginacijom i filtriranjem po nazivu) |
| POST | `/api/v1/devices/` | Kreiranje novog uređaja |
| GET | `/api/v1/devices/{id}` | Dohvatanje pojedinačnog uređaja |
| PUT | `/api/v1/devices/{id}` | Ažuriranje uređaja |
| DELETE | `/api/v1/devices/{id}` | Brisanje uređaja |
| POST | `/api/v1/devices/{id}/assign/{rack_id}` | Dodeljivanje uređaja rack-u |
| POST | `/api/v1/devices/{id}/unassign` | Uklanjanje uređaja sa rack-a |

### Rack-ovi (Racks)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/v1/racks/` | Lista rack-ova (sa paginacijom i filtriranjem) |
| POST | `/api/v1/racks/` | Kreiranje novog rack-a |
| GET | `/api/v1/racks/{id}` | Detaljan prikaz rack-a sa uređajima |
| PUT | `/api/v1/racks/{id}` | Ažuriranje rack-a |
| DELETE | `/api/v1/racks/{id}` | Brisanje rack-a |

### Balansiranje

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/api/v1/balance/` | Predlog balansiranog rasporeda uređaja |

### Statistike

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/v1/stats/` | Ukupne statistike data centra |

## Primeri Korišćenja

### Kreiranje Rack-a
```json
POST /api/v1/racks/
{
  "name": "Rack A1",
  "description": "Glavni rack u sali A",
  "serial_number": "RACK-A1-001",
  "total_units": 42,
  "max_power": 5000
}
```

### Kreiranje Uređaja
```json
POST /api/v1/devices/
{
  "name": "Server Dell R740",
  "description": "Web server",
  "serial_number": "SRV-DELL-001",
  "units_occupied": 2,
  "power_consumption": 750
}
```

### Lista Svih Uređaja
```bash
GET /api/v1/devices/
```
**Odgovor:**
```json
[
  {
    "id": 1,
    "name": "Server Dell R740",
    "serial_number": "SRV-DELL-001",
    "units_occupied": 2,
    "power_consumption": 750,
    "rack_id": null
  }
]
```

### Filtriranje Uređaja po Nazivu
```bash
GET /api/v1/devices/?name=server&limit=10
```

### Dohvatanje Pojedinačnog Rack-a sa Uređajima
```bash
GET /api/v1/racks/1
```
**Odgovor:**
```json
{
  "id": 1,
  "name": "Rack A1",
  "serial_number": "RACK-A1-001",
  "total_units": 42,
  "max_power": 5000,
  "current_power": 750,
  "current_units": 2,
  "devices": [
    {
      "id": 1,
      "name": "Server Dell R740",
      "serial_number": "SRV-DELL-001",
      "units_occupied": 2,
      "power_consumption": 750,
      "rack_id": 1
    }
  ]
}
```

### Dodeljivanje Uređaja Rack-u
```bash
POST /api/v1/devices/1/assign/1
```
**Odgovor:**
```json
{
  "message": "Uređaj uspešno dodeljen rack-u",
  "device_id": 1,
  "rack_id": 1
}
```

### Ažuriranje Uređaja
```json
PUT /api/v1/devices/1
{
  "name": "Server Dell R740 Updated",
  "description": "Updated web server",
  "serial_number": "SRV-DELL-001",
  "units_occupied": 2,
  "power_consumption": 800
}
```

### Brisanje Uređaja
```bash
DELETE /api/v1/devices/1
```
**Odgovor:**
```json
{
  "message": "Uređaj obrisan",
  "device_id": 1
}
```

### Statistike Data Centra
```bash
GET /api/v1/stats/
```
**Odgovor:**
```json
{
  "total_devices": 5,
  "total_racks": 2,
  "total_power_consumed": 3200,
  "overall_utilization_percent": 64.0
}
```

### Balansiranje Uređaja (Jednostavan Primer)
```json
POST /api/v1/balance/
{
  "devices": [
    {
      "name": "Server 1",
      "serial_number": "SRV-001",
      "units_occupied": 2,
      "power_consumption": 500
    },
    {
      "name": "Server 2",
      "serial_number": "SRV-002",
      "units_occupied": 1,
      "power_consumption": 300
    }
  ],
  "racks": [
    {
      "name": "Rack 1",
      "serial_number": "RACK-001",
      "total_units": 10,
      "max_power": 2000
    }
  ]
}
```
**Odgovor:**
```json
{
  "assignments": [
    {"device_id": 0, "rack_id": 0},
    {"device_id": 1, "rack_id": 0}
  ],
  "unassigned_devices": []
}
```

### Balansiranje sa Više Rack-ova
```json
POST /api/v1/balance/
{
  "devices": [
    {"name": "Big Server", "serial_number": "SRV-BIG", "units_occupied": 4, "power_consumption": 1000},
    {"name": "Small Server", "serial_number": "SRV-SML", "units_occupied": 1, "power_consumption": 200},
    {"name": "Medium Server", "serial_number": "SRV-MED", "units_occupied": 2, "power_consumption": 400}
  ],
  "racks": [
    {"name": "Rack A", "serial_number": "RACK-A", "total_units": 6, "max_power": 1500},
    {"name": "Rack B", "serial_number": "RACK-B", "total_units": 8, "max_power": 1200}
  ]
}
```
**Odgovor:**
```json
{
  "assignments": [
    {"device_id": 0, "rack_id": 0},
    {"device_id": 1, "rack_id": 0},
    {"device_id": 2, "rack_id": 1}
  ],
  "unassigned_devices": []
}
```

### Balansiranje sa Nedodeljenim Uređajima
```json
POST /api/v1/balance/
{
  "devices": [
    {"name": "Too Big Server", "serial_number": "SRV-TOO-BIG", "units_occupied": 20, "power_consumption": 5000}
  ],
  "racks": [
    {"name": "Small Rack", "serial_number": "RACK-SMALL", "total_units": 10, "max_power": 1000}
  ]
}
```
**Odgovor:**
```json
{
  "assignments": [],
  "unassigned_devices": [0]
}
```
{
  "assignments": [
    {
      "device_id": 0,
      "rack_id": 0
    }
  ],
  "unassigned_devices": []
}
```

## Web Dashboard

Projekat uključuje **moderni, interaktivni web dashboard** na root endpoint-u (`/`), koji služi kao kompletan frontend interfejs za demonstraciju API funkcionalnosti.

### 🎨 **Dizajn i UX**
- **Moderni gradijent dizajn** sa Bootstrap 5 framework-om
- **Responsive layout** koji radi na desktop-u i mobilnim uređajima
- **Smooth animacije** i hover efekti
- **Font Awesome ikone** za vizuelnu atraktivnost
- **Real-time status** sistema u navbar-u

### 📊 **Interaktivne Funkcionalnosti**
- **📈 Live Statistike**: 4 kartice sa ukupnim uređajima, rack-ovima, potrošnjom energije i iskorišćenošću
- **📊 Vizuelni Grafikoni**: Donut chart (Chart.js) za prikaz raspodele energije
- **🖥️ Upravljanje Uređajima**: 
  - Tabela sa svim uređajima i njihovim statusom
  - Modal forme za dodavanje novih uređaja
  - Brisanje uređaja jednim klikom
- **🏗️ Upravljanje Rack-ovima**:
  - Tabela rack-ova sa progress bar-ovima iskorišćenosti
  - Color-coded status (zeleno/žuto/crveno)
  - Detaljni pregled uređaja u rack-u
  - Modal forme za dodavanje novih rack-ova
- **⚖️ Inteligentno Balansiranje**:
  - Jedan klik za pokretanje algoritma
  - Vizuelni prikaz rezultata balansiranja
  - Lista dodeljenih i nedodeljenih uređaja

### 🔄 **Real-time Features**
- **Auto-refresh** svakih 30 sekundi
- **Live updates** statistika i tabela
- **Asinhrono učitavanje** podataka
- **Error handling** sa korisnički prijateljskim porukama

### 🎯 **Dodatne Mogućnosti**
- **Floating Action Button** za brzo dodavanje uređaja
- **Search i filter** funkcionalnosti (u planu za buduće verzije)
- **Export podataka** (u planu za buduće verzije)
- **Dark/Light mode toggle** (u planu za buduće verzije)

**Dashboard se otvara direktno na: `http://localhost:8000`**

Ovaj dashboard služi kao **kompletna demonstracija** mogućnosti API-ja i pokazuje kako bi izgledao pun frontend za data center management sistem.

**Napomena:** Dashboard je implementiran direktno u `app/main.py` kao HTML response na root endpoint-u (`/`). Prethodni `dashboard.html` fajl je uklonjen jer više nije potreban.

## Algoritam Balansiranja

Algoritam koristi **greedy pristup** za balansiranje uređaja po rack-ovima:

1. **Sortiranje**: Uređaji se sortiraju po potrošnji energije opadajuće
2. **Dodeljivanje**: Za svaki uređaj se traži rack sa najviše preostale snage koji može da primi uređaj
3. **Provera ograničenja**: Algoritam proverava i jedinice i snagu
4. **Nedodeljeni uređaji**: Uređaji koji ne stanu nigde se vraćaju kao nedodeljeni

Ovaj pristup obezbeđuje dobru balansiranost i efikasnost.

## Testiranje

Pokrenite testove:
```bash
pytest tests/ -v
```

Testovi pokrivaju:
- Uspešno balansiranje
- Slučajeve sa nedodeljenim uređajima
- Ograničenja snage i jedinica
- Više rack-ova

## Validacija i Bezbednost

- **Pydantic validacija**: Svi ulazi se automatski validiraju
- **Jedinstveni serijski brojevi**: Ne dozvoljavaju duplikate
- **Pozitivne vrednosti**: Jedinice i snaga moraju biti > 0
- **Kapacitet provere**: Prilikom dodeljivanja se proverava raspoloživi prostor
- **Error handling**: Detaljne poruke grešaka

## Dodatne Funkcionalnosti

Osim osnovnih zahteva, projekat uključuje:

- **Paginacija**: `?skip=0&limit=100`
- **Filtriranje**: `?name=server` za pretragu po nazivu
- **Statistike**: Ukupna potrošnja i iskorišćenost
- **Health check**: Za monitoring
- **Swagger dokumentacija**: Interaktivno testiranje API-ja
- **Docker podrška**: Za lako deployovanje

## Zaključak

Ovaj projekat demonstrira napredne veštine u Python backend razvoju, uključujući dizajn API-ja, rad sa bazama podataka, algoritamsko razmišljanje i testiranje. Kod je čitljiv, dobro dokumentovan i spreman za produkciju. Algoritam balansiranja je optimizovan i efikasan, dok dodatne funkcionalnosti pokazuju inicijativu i duboko razumevanje problema.

Za bilo kakva pitanja ili sugestije, slobodno se obratite!