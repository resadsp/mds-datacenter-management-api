import os

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.database import engine, ensure_sqlite_schema_updates
from app import models
from app.auth import bootstrap_default_users
from app.middleware import configure_middlewares, get_metrics_payload
from app.routers import devices, racks, balancing, stats, seed, auth, audit_logs

try:
    import redis
except Exception:  # pragma: no cover
    redis = None

# Kreiramo tabele u bazi ako ne postoje
models.Base.metadata.create_all(bind=engine)
ensure_sqlite_schema_updates()
bootstrap_default_users()

# Inicijalizacija FastAPI aplikacije sa osnovnim informacijama
app = FastAPI(
    title="Data Center Management API",
    description="API za upravljanje uređajima i rack-ovima u data centru, praćenje potrošnje energije i predloge balansiranog rasporeda.",
    version="1.0.0"
)

allowed_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
configure_middlewares(app)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Uključujemo rutere sa prefiksom /api/v1 za organizovanu strukturu API-ja
app.include_router(devices.router, prefix="/api/v1", tags=["Uređaji"])
app.include_router(racks.router, prefix="/api/v1", tags=["Rack-ovi"])
app.include_router(balancing.router, prefix="/api/v1", tags=["Balansiranje"])
app.include_router(stats.router, prefix="/api/v1", tags=["Statistike"])
app.include_router(seed.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _build_error_payload(detail: str, code: str, request_id: str, errors=None):
    payload = {
        "detail": detail,
        "code": code,
        "request_id": request_id,
    }
    if errors is not None:
        payload["errors"] = errors
    return payload


def _sanitize_for_json(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {key: _sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_for_json(item) for item in value)
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = _request_id(request)
    sanitized_errors = _sanitize_for_json(exc.errors())
    return JSONResponse(
        status_code=422,
        content=_build_error_payload(
            detail="Validation failed",
            code="validation_error",
            request_id=request_id,
            errors=sanitized_errors,
        ),
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = _request_id(request)
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(
            detail=detail,
            code="http_error",
            request_id=request_id,
        ),
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return await http_exception_handler(request, HTTPException(status_code=exc.status_code, detail=exc.detail))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _request_id(request)
    return JSONResponse(
        status_code=500,
        content=_build_error_payload(
            detail="Internal server error",
            code="internal_error",
            request_id=request_id,
        ),
        headers={"X-Request-ID": request_id} if request_id else None,
    )


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "zdravo"}


@app.get("/health/live")
def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready():
    checks = {"database": "ok", "redis": "skipped"}
    overall_status = "ready"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
        overall_status = "not_ready"

    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        if redis is None:
            checks["redis"] = "unavailable"
            overall_status = "not_ready"
        else:
            try:
                redis_client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=0.2)
                redis_client.ping()
                checks["redis"] = "ok"
            except Exception:
                checks["redis"] = "error"
                overall_status = "not_ready"

    status_code = 200 if overall_status == "ready" else 503
    return JSONResponse(status_code=status_code, content={"status": overall_status, "checks": checks})


@app.get("/metrics", include_in_schema=False)
def metrics():
    payload, content_type = get_metrics_payload()
    return Response(content=payload, media_type=content_type)

# Login stranica na root endpoint-u
@app.get("/", response_class=HTMLResponse)
def get_login_page():
    return """
<!DOCTYPE html>
<html lang="sr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prijava - Data Center Management System</title>
    <link rel="icon" type="image/png" href="/static/images/mds.png">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: #e6f4ff; min-height: 100vh; display: flex; align-items: center; }
        .login-card { background: #ffffff; border: none; border-radius: 16px; box-shadow: 0 16px 40px rgba(0,0,0,.18); }
        .login-title {
            font-size: 1.7rem;
            font-weight: 700;
            letter-spacing: 0.2px;
            color: #1f3556;
        }
        .login-subtitle {
            font-size: 1rem;
            font-weight: 500;
            color: #5f728b;
        }
        .login-form-label {
            font-size: 0.98rem;
            font-weight: 600;
            color: #1f3556;
        }
        .login-submit-btn {
            background: #2f80ed;
            border-color: #2f80ed;
            color: #fff;
            font-size: 1.02rem;
            font-weight: 600;
            padding-top: 0.6rem;
            padding-bottom: 0.6rem;
        }
        .login-submit-btn:hover {
            background: #1f6fd6;
            border-color: #1f6fd6;
            color: #fff;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-5 col-lg-4">
                <div class="card login-card">
                    <div class="card-body p-4">
                        <h4 class="text-center mb-3 login-title"><i class="fas fa-user-lock"></i> Prijava</h4>
                        <p class="text-center mb-4 login-subtitle">Data Center Management System</p>
                        <form id="loginForm">
                            <div class="mb-3">
                                <label class="form-label login-form-label">Korisničko ime</label>
                                <input type="text" class="form-control" id="username" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label login-form-label">Lozinka</label>
                                <input type="password" class="form-control" id="password" required>
                            </div>
                            <button type="submit" class="btn login-submit-btn w-100">Prijavi se</button>
                        </form>
                        <div id="feedback" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const TOKEN_KEY = "mds_token";
        const REFRESH_TOKEN_KEY = "mds_refresh_token";
        const USER_KEY = "mds_user";
        const DEVICE_FILTERS_KEY = "mds_device_filters";
        const RACK_FILTERS_KEY = "mds_rack_filters";

        async function login(username, password) {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload?.detail || 'Neuspešna prijava.');
            }
            localStorage.setItem(TOKEN_KEY, payload.access_token);
            if (payload.refresh_token) {
                localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
            }

            const meResp = await fetch('/api/v1/auth/me', {
                headers: { 'Authorization': `Bearer ${payload.access_token}` }
            });
            const mePayload = await meResp.json();
            if (!meResp.ok) {
                throw new Error(mePayload?.detail || 'Neuspešno učitavanje profila.');
            }
            localStorage.setItem(USER_KEY, JSON.stringify(mePayload));
            window.location.href = '/dashboard';
        }

        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const feedback = document.getElementById('feedback');
            feedback.innerHTML = '';
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            try {
                await login(username, password);
            } catch (err) {
                feedback.innerHTML = `<div class="alert alert-danger mb-0">${err.message}</div>`;
            }
        });
    </script>
</body>
</html>
    """

# Glavni dashboard endpoint
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return """
<!DOCTYPE html>
<html lang="sr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Data Center Management System</title>
    <link rel="icon" type="image/png" href="/static/images/mds.png">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #e6f4ff; min-height: 100vh; }
        .navbar { background: rgba(255,255,255,0.95) !important; backdrop-filter: blur(10px); }
        .card { border: 1px solid #d7e8fb; border-radius: 15px; box-shadow: 0 4px 12px rgba(20, 80, 140, 0.08); transition: transform 0.25s; }
        .card:hover { transform: translateY(-5px); }
        .dashboard-container > .row {
            margin-bottom: 3rem !important;
        }
        .btn-primary, .btn-success, .btn-danger, .btn-warning {
            background: #2f80ed;
            border: 1px solid #2f80ed;
            color: #fff;
        }
        .btn-primary:hover, .btn-success:hover, .btn-danger:hover, .btn-warning:hover {
            background: #1f6fd6;
            border-color: #1f6fd6;
            color: #fff;
        }
        .bg-success, .bg-info, .bg-warning, .bg-danger { background-color: #2f80ed !important; color: #fff !important; }
        .bg-warning.text-dark { color: #fff !important; }
        .progress-bar.bg-success, .progress-bar.bg-warning, .progress-bar.bg-danger { background-color: #2f80ed !important; }
        .text-success, .text-warning, .text-info { color: #2f80ed !important; }
        .stats-card { background: rgba(255,255,255,0.9); border-radius: 15px; padding: 20px; margin: 10px; }
        .chart-container { position: relative; height: 300px; }
        .form-control:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,0.25); }
        .table { border-radius: 10px; overflow: hidden; }
        .badge { font-size: 0.8em; }
        .alert { border-radius: 10px; }
        .progress { border-radius: 10px; height: 20px; }
        .modal-content { border-radius: 15px; }
        .floating-btn { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
        .floating-alerts {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 2000;
            width: min(420px, calc(100vw - 40px));
        }
        .alert-toast {
            margin-bottom: 10px;
            animation: slideIn 0.2s ease-out;
        }
        @keyframes slideIn {
            from { transform: translateX(20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .toast-stack {
            position: fixed;
            top: 16px;
            right: 16px;
            z-index: 3000;
            width: min(420px, calc(100vw - 32px));
        }

        .toast-item {
            border-radius: 10px;
            margin-bottom: 10px;
            box-shadow: 0 3px 10px rgba(20, 80, 140, 0.08);
            animation: slideIn .18s ease-out;
        }

        .inline-feedback {
            margin-top: 10px;
        }

        .action-btn-group {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            flex-wrap: nowrap;
            width: 100%;
        }

        .action-btn-group .btn {
            min-width: 34px;
        }

        #devicesTable th:last-child,
        #devicesTable td:last-child,
        #racksTable th:last-child,
        #racksTable td:last-child {
            width: 120px;
            text-align: center;
            vertical-align: middle;
            white-space: nowrap;
        }

        .action-cta {
            border-radius: 10px;
            padding: 0.45rem 0.85rem;
            font-size: 0.92rem;
            font-weight: 600;
            line-height: 1.25;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            min-width: 210px;
        }

        .balancing-actions {
            margin-top: 1rem;
        }

        @media (max-width: 576px) {
            .balancing-actions {
                width: 100%;
            }

            .balancing-actions .action-cta {
                width: 100%;
                min-width: 0;
            }
        }

        @keyframes slideIn {
            from { transform: translateY(-6px); opacity: 0; }
            to   { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light mb-4">
        <div class="container">
            <a class="navbar-brand fw-bold" href="#">
                <i class="fas fa-server text-primary"></i> Data Center Management System
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text me-3">
                    <i class="fas fa-circle text-primary"></i> Sistem Aktivan
                </span>
                <span id="userInfo" class="navbar-text me-3 text-muted"></span>
                <button id="navRunBalancingBtn" class="btn btn-outline-primary btn-sm ms-2 operator-only d-none" onclick="runBalancing()">
                    <i class="fas fa-magic"></i> Pokreni balansiranje
                </button>
                <button id="navSeedBtn" class="btn btn-outline-primary btn-sm ms-2 admin-only d-none" onclick="runSeed()">
                    <i class="fas fa-database"></i> Seed demo podaci
                </button>
                <button class="btn btn-outline-primary btn-sm ms-3" onclick="location.reload()">
                    <i class="fas fa-sync-alt"></i> Osveži
                </button>
                <button id="loginBtn" class="btn btn-outline-primary btn-sm ms-2" onclick="window.location.href='/'">
                    <i class="fas fa-sign-in-alt"></i> Login
                </button>
                <button id="logoutBtn" class="btn btn-outline-primary btn-sm ms-2 d-none" onclick="openLogoutModal()">
                    <i class="fas fa-sign-out-alt"></i> Odjava
                </button>
            </div>
        </div>
    </nav>

    <div class="container dashboard-container">
        <div id="balancingResult" class="mb-4"></div>
        <!-- Statistike -->
        <div class="row mb-4" id="statsRow">
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <i class="fas fa-desktop fa-2x text-primary mb-2"></i>
                    <h4 id="totalDevices">-</h4>
                    <p class="text-muted mb-0">Ukupno Uređaja</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <i class="fas fa-archive fa-2x text-primary mb-2"></i>
                    <h4 id="totalRacks">-</h4>
                    <p class="text-muted mb-0">Ukupno Rack-ova</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <i class="fas fa-bolt fa-2x text-primary mb-2"></i>
                    <h4 id="totalPower">-</h4>
                    <p class="text-muted mb-0">Potrošnja (W)</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <i class="fas fa-chart-pie fa-2x text-primary mb-2"></i>
                    <h4 id="utilization">-</h4>
                    <p class="text-muted mb-0">Iskorišćenost (%)</p>
                </div>
            </div>
        </div>

        <!-- Grafikon -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0"><i class="fas fa-chart-bar"></i> Vizuelni Pregled</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="overviewChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Uređaji i Rack-ovi -->
        <div class="row mb-4">
            <div class="col-lg-6">
                <div class="card">
                    <div class="card-header bg-success text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0"><i class="fas fa-desktop"></i> Uređaji</h5>
                        <button class="btn btn-light btn-sm operator-only" data-bs-toggle="modal" data-bs-target="#addDeviceModal">
                            <i class="fas fa-plus"></i> Dodaj
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="row g-2 mb-3">
                            <div class="col-md-6">
                                <input type="text" id="deviceSearch" class="form-control form-control-sm" placeholder="Pretraga: naziv ili serijski broj uređaja">
                            </div>
                            <div class="col-md-4 d-flex align-items-center gap-3 flex-wrap">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="deviceOnlyFree">
                                    <label class="form-check-label" for="deviceOnlyFree">Samo slobodni</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="deviceIncludeArchived">
                                    <label class="form-check-label" for="deviceIncludeArchived">Prikaži arhivirane</label>
                                </div>
                            </div>
                            <div class="col-md-2 text-end">
                                <button class="btn btn-outline-secondary btn-sm" onclick="resetDeviceFilters()">
                                    Reset
                                </button>
                            </div>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-hover" id="devicesTable">
                                <thead>
                                    <tr>
                                        <th>Naziv</th>
                                        <th>Serijski</th>
                                        <th>Jedinice</th>
                                        <th>Snaga</th>
                                        <th>Status</th>
                                        <th>Akcije</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-6">
                <div class="card">
                    <div class="card-header bg-info text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0"><i class="fas fa-archive"></i> Rack-ovi</h5>
                        <button class="btn btn-light btn-sm operator-only" data-bs-toggle="modal" data-bs-target="#addRackModal">
                            <i class="fas fa-plus"></i> Dodaj
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="row g-2 mb-3">
                            <div class="col-md-6">
                                <input type="text" id="rackSearch" class="form-control form-control-sm" placeholder="Pretraga: naziv ili serijski broj rack-a">
                            </div>
                            <div class="col-md-2">
                                <select id="rackLoadFilter" class="form-select form-select-sm">
                                    <option value="all">Svi statusi</option>
                                    <option value="low">Nisko</option>
                                    <option value="medium">Srednje</option>
                                    <option value="high">Visoko</option>
                                </select>
                            </div>
                            <div class="col-md-2 d-flex align-items-center">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="rackIncludeArchived">
                                    <label class="form-check-label" for="rackIncludeArchived">Arhivirani</label>
                                </div>
                            </div>
                            <div class="col-md-2 text-end">
                                <button class="btn btn-outline-secondary btn-sm" onclick="resetRackFilters()">
                                    Reset
                                </button>
                            </div>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-hover" id="racksTable">
                                <thead>
                                    <tr>
                                        <th>Naziv</th>
                                        <th>Serijski</th>
                                        <th>Jedinice</th>
                                        <th>Iskorišćenost</th>
                                        <th>Status</th>
                                        <th>Akcije</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mb-4 admin-only d-none" id="auditLogsSection">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0"><i class="fas fa-clipboard-list"></i> Audit Logovi</h5>
                        <button class="btn btn-light btn-sm" onclick="loadAuditLogs()">
                            <i class="fas fa-sync-alt"></i> Osveži
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm table-hover" id="auditLogsTable">
                                <thead>
                                    <tr>
                                        <th>Vreme</th>
                                        <th>Korisnik</th>
                                        <th>Akcija</th>
                                        <th>Entitet</th>
                                        <th>ID entiteta</th>
                                        <th>Audit ID</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                        <div class="d-flex justify-content-between align-items-center">
                            <small id="auditLogsMeta" class="text-muted"></small>
                            <div>
                                <button id="auditPrevBtn" class="btn btn-outline-secondary btn-sm" onclick="changeAuditPage(-1)">Prethodna</button>
                                <button id="auditNextBtn" class="btn btn-outline-secondary btn-sm ms-2" onclick="changeAuditPage(1)">Sledeća</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modali za dodavanje -->

    <!-- Logout Modal -->
    <div class="modal fade" id="logoutModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-sign-out-alt"></i> Odjava</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    Izaberi način odjave:
                </div>
                <div class="modal-footer d-grid gap-2">
                    <button type="button" class="btn btn-primary w-100 m-0" data-bs-dismiss="modal">Otkaži</button>
                    <button type="button" class="btn btn-primary w-100 m-0" onclick="logoutCurrentSession()">
                        Odjavi se sa ovog uređaja
                    </button>
                    <button type="button" class="btn btn-primary w-100 m-0" onclick="logoutAllSessions()">
                        Odjavi se sa svih uređaja
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Add Device Modal -->
    <div class="modal fade" id="addDeviceModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-desktop"></i> Dodaj Uređaj</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="addDeviceForm">
                        <div class="mb-3">
                            <label class="form-label">Naziv</label>
                            <input type="text" class="form-control" id="deviceName" name="name" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Opis</label>
                            <input type="text" class="form-control" id="deviceDesc" name="description">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Serijski Broj</label>
                            <input type="text" class="form-control" id="deviceSerial" name="serial_number" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label">Jedinice</label>
                                <input type="number" class="form-control" id="deviceUnits" name="units_occupied" min="1" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Snaga (W)</label>
                                <input type="number" class="form-control" id="devicePower" name="power_consumption" min="1" required>
                            </div>
                        </div>
                    </form>
                    <div id="deviceFeedback"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Otkaži</button>
                    <button type="button" class="btn btn-primary" onclick="addDevice()">Dodaj Uređaj</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Add Rack Modal -->
    <div class="modal fade" id="addRackModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-archive"></i> Dodaj Rack</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="addRackForm">
                        <div class="mb-3">
                            <label class="form-label">Naziv</label>
                            <input type="text" class="form-control" id="rackName" name="name" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Opis</label>
                            <input type="text" class="form-control" id="rackDesc" name="description">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Serijski Broj</label>
                            <input type="text" class="form-control" id="rackSerial" name="serial_number" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label">Ukupno Jedinica</label>
                                <input type="number" class="form-control" id="rackUnits" name="total_units" min="1" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Maks. Snaga (W)</label>
                                <input type="number" class="form-control" id="rackPower" name="max_power" min="1" required>
                            </div>
                        </div>
                    </form>
                    <div id="rackFeedback"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Otkaži</button>
                    <button type="button" class="btn btn-success" onclick="addRack()">Dodaj Rack</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Edit Device Modal -->
    <div class="modal fade" id="editDeviceModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-pen"></i> Izmeni Uređaj</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="editDeviceForm">
                        <input type="hidden" id="editDeviceId">
                        <input type="hidden" id="editDeviceVersion">
                        <div class="mb-3">
                            <label class="form-label">Naziv</label>
                            <input type="text" class="form-control" id="editDeviceName" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Opis</label>
                            <input type="text" class="form-control" id="editDeviceDesc">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Serijski Broj</label>
                            <input type="text" class="form-control" id="editDeviceSerial" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label">Jedinice</label>
                                <input type="number" class="form-control" id="editDeviceUnits" min="1" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Snaga (W)</label>
                                <input type="number" class="form-control" id="editDevicePower" min="1" required>
                            </div>
                        </div>
                    </form>
                    <div id="editDeviceFeedback"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Otkaži</button>
                    <button type="button" class="btn btn-primary" onclick="updateDevice()">Sačuvaj</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Edit Rack Modal -->
    <div class="modal fade" id="editRackModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-pen"></i> Izmeni Rack</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="editRackForm">
                        <input type="hidden" id="editRackId">
                        <input type="hidden" id="editRackVersion">
                        <div class="mb-3">
                            <label class="form-label">Naziv</label>
                            <input type="text" class="form-control" id="editRackName" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Opis</label>
                            <input type="text" class="form-control" id="editRackDesc">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Serijski Broj</label>
                            <input type="text" class="form-control" id="editRackSerial" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label">Ukupno Jedinica</label>
                                <input type="number" class="form-control" id="editRackUnits" min="1" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Maks. Snaga (W)</label>
                                <input type="number" class="form-control" id="editRackPower" min="1" required>
                            </div>
                        </div>
                    </form>
                    <div id="editRackFeedback"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Otkaži</button>
                    <button type="button" class="btn btn-success" onclick="updateRack()">Sačuvaj</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Assign Device Modal -->
    <div class="modal fade" id="assignDeviceModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-link"></i> Dodeli uređaj rack-u</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="assignDeviceId">
                    <div class="mb-2 text-muted small">Uređaj: <span id="assignDeviceName">-</span></div>
                    <div class="mb-3">
                        <label class="form-label">Izaberi rack</label>
                        <select id="assignRackSelect" class="form-select"></select>
                    </div>
                    <div id="assignFeedback"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Otkaži</button>
                    <button type="button" class="btn btn-primary" onclick="confirmAssignDevice()">Dodeli</button>
                </div>
            </div>
        </div>
    </div>

    <!-- View Rack Details Modal -->
    <div class="modal fade" id="viewRackModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-archive"></i> Detalji Rack-a</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="rackDetailsContent">
                    <!-- Detalji će biti učitani ovde -->
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Zatvori</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Floating Action Button -->
    <div class="floating-btn operator-only">
        <button class="btn btn-primary btn-lg rounded-circle" data-bs-toggle="modal" data-bs-target="#addDeviceModal">
            <i class="fas fa-plus"></i>
        </button>
    </div>

    <div id="floatingAlerts" class="floating-alerts"></div>

    <div id="toastStack" class="toast-stack" aria-live="polite" aria-atomic="true"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const API_BASE = "/api/v1";
        const TOKEN_KEY = "mds_token";
        const REFRESH_TOKEN_KEY = "mds_refresh_token";
        const USER_KEY = "mds_user";
        const DEVICE_FILTERS_KEY = "mds_device_filters";
        const RACK_FILTERS_KEY = "mds_rack_filters";
        let authToken = localStorage.getItem(TOKEN_KEY) || null;
        let refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY) || null;
        let currentUser = null;
        let auditPage = 1;
        let auditPageSize = 10;
        let auditTotal = 0;
        const deviceCache = new Map();
        const rackCache = new Map();
        let latestBalancingPlan = [];

        function clearBalancingPlan() {
            latestBalancingPlan = [];
            const applyBtn = document.getElementById('applyBalancingBtn');
            if (applyBtn) applyBtn.classList.add('d-none');
        }

        function refreshBalancingApplyButton() {
            const applyBtn = document.getElementById('applyBalancingBtn');
            if (!applyBtn) return;
            if (isOperatorOrAdmin() && latestBalancingPlan.length > 0) {
                applyBtn.classList.remove('d-none');
            } else {
                applyBtn.classList.add('d-none');
            }
        }

        function rejectBalancingProposal() {
            clearBalancingPlan();
            document.getElementById('balancingResult').innerHTML = `
                <div class="alert alert-secondary mb-0">
                    <i class="fas fa-ban"></i> Predlog je odbačen. Podaci nisu menjani.
                </div>
            `;
            toast('Predlog je odbačen.', 'info');
        }

        function renderDevicesTable() {
            const tbody = document.querySelector('#devicesTable tbody');
            if (!tbody) return;

            const search = (document.getElementById('deviceSearch')?.value || '').trim().toLowerCase();
            const onlyFree = document.getElementById('deviceOnlyFree')?.checked === true;
            const includeArchivedOnly = document.getElementById('deviceIncludeArchived')?.checked === true;

            let devices = Array.from(deviceCache.values());
            if (includeArchivedOnly) {
                devices = devices.filter(device => !!device.deleted_at);
            }
            if (search) {
                devices = devices.filter(device =>
                    device.name.toLowerCase().includes(search) ||
                    device.serial_number.toLowerCase().includes(search)
                );
            }
            if (onlyFree && !includeArchivedOnly) {
                devices = devices.filter(device => !device.rack_id);
            }

            function rackLabelForDevice(device) {
                if (!device.rack_id || device.deleted_at) return '';
                const rack = rackCache.get(device.rack_id);
                if (rack && rack.serial_number) return rack.serial_number;
                return `ID ${device.rack_id}`;
            }

            tbody.innerHTML = devices.map(device => `
                <tr>
                    <td>${device.name}</td>
                    <td>${device.serial_number}</td>
                    <td>${device.units_occupied}U</td>
                    <td>${device.power_consumption}W</td>
                    <td>
                        <div>
                            <span class="badge bg-${device.deleted_at ? 'dark' : (device.rack_id ? 'success' : 'secondary')}">
                                ${device.deleted_at ? 'Arhiviran' : (device.rack_id ? 'Dodeljen' : 'Slobodan')}
                            </span>
                            ${device.rack_id && !device.deleted_at ? `<div class="small text-muted mt-1">Rack: ${rackLabelForDevice(device)}</div>` : ''}
                        </div>
                    </td>
                    <td>
                        <div class="action-btn-group">
                            <button class="btn btn-sm btn-outline-secondary ${(isOperatorOrAdmin() && !device.deleted_at && !device.rack_id) ? '' : 'd-none'}" onclick="openAssignDeviceModal(${device.id})" title="Dodeli uređaj rack-u">
                                <i class="fas fa-link"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-warning ${(isOperatorOrAdmin() && !device.deleted_at && device.rack_id) ? '' : 'd-none'}" onclick="unassignDevice(${device.id})" title="Ukloni uređaj sa rack-a">
                                <i class="fas fa-unlink"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-primary ${(isOperatorOrAdmin() && !device.deleted_at) ? '' : 'd-none'}" onclick="openEditDevice(${device.id})" title="Izmeni uređaj">
                                <i class="fas fa-pen"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger ${(isOperatorOrAdmin() && !device.deleted_at) ? '' : 'd-none'}" onclick="deleteDevice(${device.id})" title="Arhiviraj uređaj">
                                <i class="fas fa-trash"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-success ${(isOperatorOrAdmin() && device.deleted_at) ? '' : 'd-none'}" onclick="restoreDevice(${device.id})" title="Vrati uređaj iz arhive">
                                <i class="fas fa-rotate-left"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        }

        function renderRacksTable() {
            const tbody = document.querySelector('#racksTable tbody');
            if (!tbody) return;

            const search = (document.getElementById('rackSearch')?.value || '').trim().toLowerCase();
            const loadFilter = document.getElementById('rackLoadFilter')?.value || 'all';
            const includeArchivedOnly = document.getElementById('rackIncludeArchived')?.checked === true;

            let racks = Array.from(rackCache.values());
            if (includeArchivedOnly) {
                racks = racks.filter(rack => !!rack.deleted_at);
            }
            if (search) {
                racks = racks.filter(rack =>
                    rack.name.toLowerCase().includes(search) ||
                    rack.serial_number.toLowerCase().includes(search)
                );
            }

            if (loadFilter !== 'all' && !includeArchivedOnly) {
                racks = racks.filter(rack => {
                    const utilization = rack.max_power > 0 ? ((rack.current_power / rack.max_power) * 100) : 0;
                    if (loadFilter === 'high') return utilization > 80;
                    if (loadFilter === 'medium') return utilization > 60 && utilization <= 80;
                    if (loadFilter === 'low') return utilization <= 60;
                    return true;
                });
            }

            tbody.innerHTML = racks.map(rack => {
                const utilization = rack.max_power > 0 ? ((rack.current_power / rack.max_power) * 100).toFixed(1) : 0;
                const statusClass = utilization > 80 ? 'danger' : utilization > 60 ? 'warning' : 'success';
                const effectiveStatusClass = rack.deleted_at ? 'dark' : statusClass;
                return `
                    <tr>
                        <td>${rack.name}</td>
                        <td>${rack.serial_number}</td>
                        <td>${rack.total_units}U</td>
                        <td>
                            <div class="progress" style="width: 100px;">
                                <div class="progress-bar bg-${statusClass}" style="width: ${utilization}%">
                                    ${utilization}%
                                </div>
                            </div>
                        </td>
                        <td>
                            <span class="badge bg-${effectiveStatusClass}">
                                ${rack.deleted_at ? 'Arhiviran' : (utilization > 80 ? 'Visoko' : utilization > 60 ? 'Srednje' : 'Nisko')}
                            </span>
                        </td>
                        <td>
                            <div class="action-btn-group">
                                <button class="btn btn-sm btn-outline-info" onclick="viewRackDetails(${rack.id})" title="Detalji rack-a">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-primary ${(isOperatorOrAdmin() && !rack.deleted_at) ? '' : 'd-none'}" onclick="openEditRack(${rack.id})" title="Izmeni rack">
                                    <i class="fas fa-pen"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger ${(isOperatorOrAdmin() && !rack.deleted_at) ? '' : 'd-none'}" onclick="deleteRack(${rack.id})" title="Arhiviraj rack">
                                    <i class="fas fa-trash"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-success ${(isOperatorOrAdmin() && rack.deleted_at) ? '' : 'd-none'}" onclick="restoreRack(${rack.id})" title="Vrati rack iz arhive">
                                    <i class="fas fa-rotate-left"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        function isOperatorOrAdmin() {
            return currentUser && (currentUser.role === 'operator' || currentUser.role === 'admin');
        }

        function saveDeviceFilters() {
            const payload = {
                search: document.getElementById('deviceSearch')?.value || '',
                onlyFree: document.getElementById('deviceOnlyFree')?.checked === true,
                includeArchived: document.getElementById('deviceIncludeArchived')?.checked === true,
            };
            localStorage.setItem(DEVICE_FILTERS_KEY, JSON.stringify(payload));
        }

        function saveRackFilters() {
            const payload = {
                search: document.getElementById('rackSearch')?.value || '',
                loadFilter: document.getElementById('rackLoadFilter')?.value || 'all',
                includeArchived: document.getElementById('rackIncludeArchived')?.checked === true,
            };
            localStorage.setItem(RACK_FILTERS_KEY, JSON.stringify(payload));
        }

        function resetDeviceFilters() {
            const searchInput = document.getElementById('deviceSearch');
            const onlyFreeInput = document.getElementById('deviceOnlyFree');
            const includeArchivedInput = document.getElementById('deviceIncludeArchived');
            if (searchInput) searchInput.value = '';
            if (onlyFreeInput) onlyFreeInput.checked = false;
            if (includeArchivedInput) includeArchivedInput.checked = false;
            localStorage.removeItem(DEVICE_FILTERS_KEY);
            loadDevices();
        }

        function resetRackFilters() {
            const searchInput = document.getElementById('rackSearch');
            const loadFilterInput = document.getElementById('rackLoadFilter');
            const includeArchivedInput = document.getElementById('rackIncludeArchived');
            if (searchInput) searchInput.value = '';
            if (loadFilterInput) loadFilterInput.value = 'all';
            if (includeArchivedInput) includeArchivedInput.checked = false;
            localStorage.removeItem(RACK_FILTERS_KEY);
            loadRacks();
        }

        function restoreDashboardFilters() {
            try {
                const rawDevice = localStorage.getItem(DEVICE_FILTERS_KEY);
                if (rawDevice) {
                    const parsed = JSON.parse(rawDevice);
                    const searchInput = document.getElementById('deviceSearch');
                    const onlyFreeInput = document.getElementById('deviceOnlyFree');
                    const includeArchivedInput = document.getElementById('deviceIncludeArchived');
                    if (searchInput) searchInput.value = parsed.search || '';
                    if (onlyFreeInput) onlyFreeInput.checked = parsed.onlyFree === true;
                    if (includeArchivedInput) includeArchivedInput.checked = parsed.includeArchived === true;
                }
            } catch {}

            try {
                const rawRack = localStorage.getItem(RACK_FILTERS_KEY);
                if (rawRack) {
                    const parsed = JSON.parse(rawRack);
                    const searchInput = document.getElementById('rackSearch');
                    const loadFilterInput = document.getElementById('rackLoadFilter');
                    const includeArchivedInput = document.getElementById('rackIncludeArchived');
                    if (searchInput) searchInput.value = parsed.search || '';
                    if (loadFilterInput) loadFilterInput.value = parsed.loadFilter || 'all';
                    if (includeArchivedInput) includeArchivedInput.checked = parsed.includeArchived === true;
                }
            } catch {}
        }

        function applyRoleUi() {
            const loginBtn = document.getElementById('loginBtn');
            const logoutBtn = document.getElementById('logoutBtn');
            const userInfo = document.getElementById('userInfo');
            const authOnly = document.querySelectorAll('.auth-only');
            const operatorOnly = document.querySelectorAll('.operator-only');
            const adminOnly = document.querySelectorAll('.admin-only');

            if (currentUser) {
                loginBtn.classList.add('d-none');
                logoutBtn.classList.remove('d-none');
                userInfo.innerHTML = `<i class="fas fa-user"></i> ${currentUser.username} (${currentUser.role})`;
            } else {
                loginBtn.classList.remove('d-none');
                logoutBtn.classList.add('d-none');
                userInfo.textContent = '';
            }

            operatorOnly.forEach(el => {
                if (isOperatorOrAdmin()) {
                    el.classList.remove('d-none');
                } else {
                    el.classList.add('d-none');
                }
            });

            authOnly.forEach(el => {
                if (currentUser) {
                    el.classList.remove('d-none');
                } else {
                    el.classList.add('d-none');
                }
            });

            adminOnly.forEach(el => {
                if (currentUser && currentUser.role === 'admin') {
                    el.classList.remove('d-none');
                } else {
                    el.classList.add('d-none');
                }
            });

            refreshBalancingApplyButton();
        }

        function saveAuthState(token, user, nextRefreshToken = null) {
            authToken = token;
            currentUser = user;
            localStorage.setItem(TOKEN_KEY, token);
            if (nextRefreshToken) {
                refreshToken = nextRefreshToken;
                localStorage.setItem(REFRESH_TOKEN_KEY, nextRefreshToken);
            }
            localStorage.setItem(USER_KEY, JSON.stringify(user));
            applyRoleUi();
        }

        function clearAuthState() {
            authToken = null;
            refreshToken = null;
            currentUser = null;
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(REFRESH_TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
            applyRoleUi();
        }

        function openLogoutModal() {
            new bootstrap.Modal(document.getElementById('logoutModal')).show();
        }

        function closeLogoutModal() {
            const el = document.getElementById('logoutModal');
            const instance = bootstrap.Modal.getInstance(el);
            if (instance) instance.hide();
        }

        async function logoutCurrentSession() {
            const tokenToRevoke = refreshToken;
            try {
                if (tokenToRevoke) {
                    await apiCall('/auth/logout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ refresh_token: tokenToRevoke }),
                    }, { skipAuth: true });
                }
            } catch {
                // Namerno ignorišemo logout grešku i čistimo lokalnu sesiju.
            } finally {
                closeLogoutModal();
                clearAuthState();
                toast('Uspešno ste se odjavili.', 'info');
                window.location.href = '/';
            }
        }

        async function logoutAllSessions() {
            try {
                await apiCall('/auth/logout-all', {
                    method: 'POST',
                });
            } catch {
                // Namerno ignorišemo logout-all grešku i čistimo lokalnu sesiju.
            } finally {
                closeLogoutModal();
                clearAuthState();
                toast('Uspešno ste odjavljeni sa svih uređaja.', 'info');
                window.location.href = '/';
            }
        }

        async function logout() {
            await logoutCurrentSession();
        }

        async function ensureSession() {
            const rawUser = localStorage.getItem(USER_KEY);
            if (!authToken) {
                window.location.href = '/';
                return false;
            }
            if (rawUser) {
                try {
                    currentUser = JSON.parse(rawUser);
                } catch {
                    currentUser = null;
                }
            }

            try {
                const user = await apiCall('/auth/me', { method: 'GET' });
                currentUser = user;
                localStorage.setItem(USER_KEY, JSON.stringify(user));
                applyRoleUi();
                return true;
            } catch {
                clearAuthState();
                window.location.href = '/';
                return false;
            }
        }

        async function refreshAccessToken() {
            if (!refreshToken) return false;
            const response = await fetch(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            const ct = response.headers.get("content-type") || "";
            const payload = ct.includes("application/json") ? await response.json() : await response.text();
            if (!response.ok || !payload?.access_token) {
                clearAuthState();
                return false;
            }
            authToken = payload.access_token;
            localStorage.setItem(TOKEN_KEY, authToken);
            if (payload.refresh_token) {
                refreshToken = payload.refresh_token;
                localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
            }
            return true;
        }

        function toast(message, type = "info", ms = 5000) {
            const stack = document.getElementById("toastStack");
            const el = document.createElement("div");
            el.className = `alert alert-${type} alert-dismissible fade show toast-item`;
            el.setAttribute("role", "alert");
            el.innerHTML = `
              <div class="me-4">${message}</div>
              <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            stack.appendChild(el);
            setTimeout(() => el.remove(), ms);
        }

        function setInlineFeedback(containerId, message, type = "danger") {
            const container = document.getElementById(containerId);
            if (!container) return;
            container.innerHTML = `
              <div class="alert alert-${type} inline-feedback" role="alert">
                ${message}
              </div>
            `;
        }

        function clearInlineFeedback(containerId) {
            const container = document.getElementById(containerId);
            if (container) container.innerHTML = "";
        }

        function parseApiError(status, payload) {
            // FastAPI 422: { detail: [{loc, msg, ...}, ...] }
            if (payload && Array.isArray(payload.detail)) {
                const parts = payload.detail.map(e => {
                    const loc = Array.isArray(e.loc) ? e.loc.join(".") : "field";
                    return `${loc}: ${e.msg}`;
                });
                return `Validacija (${status}): ${parts.join(" | ")}`;
            }

            if (payload?.detail && typeof payload.detail === "string") {
                return `Greška ${status}: ${payload.detail}`;
            }

            if (payload?.message && typeof payload.message === "string") {
                return `Greška ${status}: ${payload.message}`;
            }

            return `Greška ${status}: Neuspešan zahtev.`;
        }

        function focusFirstInvalidField(payload) {
            if (!payload || !Array.isArray(payload.detail)) return;
            const first = payload.detail.find(e => Array.isArray(e.loc) && e.loc.includes("body"));
            if (!first) return;

            const field = first.loc[first.loc.length - 1];
            const map = {
                name: ["deviceName", "rackName"],
                description: ["deviceDesc", "rackDesc"],
                serial_number: ["deviceSerial", "rackSerial"],
                units_occupied: ["deviceUnits"],
                power_consumption: ["devicePower"],
                total_units: ["rackUnits"],
                max_power: ["rackPower"]
            };

            const candidates = map[field] || [];
            for (const id of candidates) {
                const input = document.getElementById(id);
                if (input && input.offsetParent !== null) {
                    input.focus();
                    return;
                }
            }
        }

        async function apiCall(endpoint, options = {}, config = {}) {
            const headers = { ...(options.headers || {}) };
            const skipAuth = config.skipAuth === true;
            const isRetry = config.isRetry === true;

            if (!skipAuth && authToken) {
                headers['Authorization'] = `Bearer ${authToken}`;
            }

            const response = await fetch(`${API_BASE}${endpoint}`, {
                ...options,
                headers,
            });
            const ct = response.headers.get("content-type") || "";
            const payload = ct.includes("application/json") ? await response.json() : await response.text();

            if (!response.ok) {
                if (response.status === 401 && !skipAuth) {
                    if (!isRetry && await refreshAccessToken()) {
                        return apiCall(endpoint, options, { ...config, isRetry: true });
                    }
                    clearAuthState();
                    window.location.href = '/';
                }
                const message = parseApiError(response.status, payload);
                const err = new Error(message);
                err.status = response.status;
                err.payload = payload;
                throw err;
            }
            return payload;
        }

        // Primer upotrebe u submit handler-u:
        // clearInlineFeedback("deviceFeedback");
        // try {
        //   await apiCall("/devices/", {...});
        //   toast("Uređaj uspešno dodat.", "success");
        //   setInlineFeedback("deviceFeedback", "Uređaj uspešno dodat.", "success");
        // } catch (e) {
        //   toast(e.message, "danger");
        //   setInlineFeedback("deviceFeedback", e.message, "danger");
        //   if (e.status === 422) focusFirstInvalidField(e.payload);
        // }

        // Load data functions
        async function loadStats() {
            const stats = await apiCall('/stats/');
            if (stats) {
                document.getElementById('totalDevices').textContent = stats.total_devices;
                document.getElementById('totalRacks').textContent = stats.total_racks;
                document.getElementById('totalPower').textContent = stats.total_power_consumed;
                document.getElementById('utilization').textContent = stats.overall_utilization_percent.toFixed(1) + '%';
            }
        }

        async function loadDevices() {
            const includeArchived = document.getElementById('deviceIncludeArchived')?.checked === true;
            const result = await apiCall(`/devices/?page=1&page_size=100&sort_by=id&sort_order=asc&include_deleted=${includeArchived ? 'true' : 'false'}`);
            const devices = result?.items || [];
            if (result) {
                deviceCache.clear();
                devices.forEach(device => deviceCache.set(device.id, device));
                renderDevicesTable();
            }
        }

        async function loadRacks() {
            const includeArchived = document.getElementById('rackIncludeArchived')?.checked === true;
            const result = await apiCall(`/racks/?page=1&page_size=100&sort_by=id&sort_order=asc&include_deleted=${includeArchived ? 'true' : 'false'}`);
            const racks = result?.items || [];
            if (result) {
                rackCache.clear();
                racks.forEach(rack => rackCache.set(rack.id, rack));
                renderRacksTable();
                renderDevicesTable();
            }
        }

        async function loadAuditLogs() {
            if (!currentUser || currentUser.role !== 'admin') return;
            const result = await apiCall(`/audit-logs/?page=${auditPage}&page_size=${auditPageSize}&sort_by=id&sort_order=desc`);
            const tbody = document.querySelector('#auditLogsTable tbody');
            const items = result?.items || [];
            const meta = result?.meta || { total: 0, page: 1, page_size: auditPageSize };
            auditTotal = meta.total || 0;

            tbody.innerHTML = items.map(log => `
                <tr>
                    <td>${new Date(log.created_at).toLocaleString('sr-RS')}</td>
                    <td>${log.actor_username}</td>
                    <td><span class="badge bg-secondary">${log.action}</span></td>
                    <td>${log.entity_type}</td>
                    <td>${log.entity_id ?? '-'}</td>
                    <td>${log.id}</td>
                </tr>
            `).join('');

            document.getElementById('auditLogsMeta').textContent = `Ukupno: ${auditTotal} | Strana: ${meta.page} | Veličina: ${meta.page_size}`;
            document.getElementById('auditPrevBtn').disabled = auditPage <= 1;
            document.getElementById('auditNextBtn').disabled = (auditPage * auditPageSize) >= auditTotal;
        }

        function changeAuditPage(delta) {
            const next = auditPage + delta;
            if (next < 1) return;
            auditPage = next;
            loadAuditLogs();
        }

        function openEditDevice(id) {
            const device = deviceCache.get(id);
            if (!device) {
                toast('Uređaj nije pronađen.', 'warning');
                return;
            }
            document.getElementById('editDeviceId').value = device.id;
            document.getElementById('editDeviceVersion').value = device.version;
            document.getElementById('editDeviceName').value = device.name;
            document.getElementById('editDeviceDesc').value = device.description || '';
            document.getElementById('editDeviceSerial').value = device.serial_number;
            document.getElementById('editDeviceUnits').value = device.units_occupied;
            document.getElementById('editDevicePower').value = device.power_consumption;
            clearInlineFeedback('editDeviceFeedback');
            new bootstrap.Modal(document.getElementById('editDeviceModal')).show();
        }

        async function updateDevice() {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }

            const id = parseInt(document.getElementById('editDeviceId').value);
            const payload = {
                name: document.getElementById('editDeviceName').value,
                description: document.getElementById('editDeviceDesc').value,
                serial_number: document.getElementById('editDeviceSerial').value,
                units_occupied: parseInt(document.getElementById('editDeviceUnits').value),
                power_consumption: parseFloat(document.getElementById('editDevicePower').value),
                version: parseInt(document.getElementById('editDeviceVersion').value),
            };

            try {
                await apiCall(`/devices/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                toast('Uređaj uspešno ažuriran.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editDeviceModal')).hide();
                await loadAllData();
            } catch (e) {
                if (e.status === 409) {
                    setInlineFeedback('editDeviceFeedback', 'Došlo je do konflikta verzije. Podaci su osveženi — pokušaj ponovo.', 'warning');
                    await loadDevices();
                    return;
                }
                setInlineFeedback('editDeviceFeedback', e.message, 'danger');
            }
        }

        function openEditRack(id) {
            const rack = rackCache.get(id);
            if (!rack) {
                toast('Rack nije pronađen.', 'warning');
                return;
            }
            document.getElementById('editRackId').value = rack.id;
            document.getElementById('editRackVersion').value = rack.version;
            document.getElementById('editRackName').value = rack.name;
            document.getElementById('editRackDesc').value = rack.description || '';
            document.getElementById('editRackSerial').value = rack.serial_number;
            document.getElementById('editRackUnits').value = rack.total_units;
            document.getElementById('editRackPower').value = rack.max_power;
            clearInlineFeedback('editRackFeedback');
            new bootstrap.Modal(document.getElementById('editRackModal')).show();
        }

        async function updateRack() {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }

            const id = parseInt(document.getElementById('editRackId').value);
            const payload = {
                name: document.getElementById('editRackName').value,
                description: document.getElementById('editRackDesc').value,
                serial_number: document.getElementById('editRackSerial').value,
                total_units: parseInt(document.getElementById('editRackUnits').value),
                max_power: parseFloat(document.getElementById('editRackPower').value),
                version: parseInt(document.getElementById('editRackVersion').value),
            };

            try {
                await apiCall(`/racks/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                toast('Rack uspešno ažuriran.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editRackModal')).hide();
                await loadAllData();
            } catch (e) {
                if (e.status === 409) {
                    setInlineFeedback('editRackFeedback', 'Došlo je do konflikta verzije. Podaci su osveženi — pokušaj ponovo.', 'warning');
                    await loadRacks();
                    return;
                }
                setInlineFeedback('editRackFeedback', e.message, 'danger');
            }
        }

        // Add functions
        async function addDevice() {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            clearInlineFeedback("deviceFeedback");

            const device = {
                name: document.getElementById('deviceName').value,
                description: document.getElementById('deviceDesc').value,
                serial_number: document.getElementById('deviceSerial').value,
                units_occupied: parseInt(document.getElementById('deviceUnits').value),
                power_consumption: parseFloat(document.getElementById('devicePower').value)
            };

            try {
                const result = await apiCall('/devices/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(device)
                });

                if (result) {
                    toast('Uređaj uspešno dodat!', 'success');
                    setInlineFeedback("deviceFeedback", "Uređaj uspešno dodat!", "success");
                    bootstrap.Modal.getInstance(document.getElementById('addDeviceModal')).hide();
                    document.getElementById('addDeviceForm').reset();
                    loadDevices();
                    loadStats();
                    initChart();
                }
            } catch (e) {
                toast(e.message, 'danger');
                setInlineFeedback("deviceFeedback", e.message, "danger");
                if (e.status === 422) focusFirstInvalidField(e.payload);
            }
        }

        async function addRack() {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            clearInlineFeedback("rackFeedback");

            const rack = {
                name: document.getElementById('rackName').value,
                description: document.getElementById('rackDesc').value,
                serial_number: document.getElementById('rackSerial').value,
                total_units: parseInt(document.getElementById('rackUnits').value),
                max_power: parseFloat(document.getElementById('rackPower').value)
            };

            try {
                const result = await apiCall('/racks/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(rack)
                });

                if (result) {
                    toast('Rack uspešno dodat!', 'success');
                    setInlineFeedback("rackFeedback", "Rack uspešno dodat!", "success");
                    bootstrap.Modal.getInstance(document.getElementById('addRackModal')).hide();
                    document.getElementById('addRackForm').reset();
                    loadRacks();
                    loadStats();
                    initChart();
                }
            } catch (e) {
                toast(e.message, 'danger');
                setInlineFeedback("rackFeedback", e.message, "danger");
                if (e.status === 422) focusFirstInvalidField(e.payload);
            }
        }

        async function deleteDevice(id) {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            if (!confirm('Da li ste sigurni da želite da obrišete ovaj uređaj?')) return;
            try {
                const result = await apiCall(`/devices/${id}`, { method: 'DELETE' });
                if (result !== null) {
                    toast('Uređaj obrisan!', 'success');
                    loadDevices();
                    loadStats();
                    initChart();
                }
            } catch (e) {
                toast(e.message, 'danger');
            }
        }

        async function openAssignDeviceModal(id) {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }

            const device = deviceCache.get(id);
            if (!device) {
                toast('Uređaj nije pronađen.', 'warning');
                return;
            }
            if (device.deleted_at) {
                toast('Arhivirani uređaj ne može biti dodeljen.', 'warning');
                return;
            }
            if (device.rack_id) {
                toast('Uređaj je već dodeljen rack-u.', 'warning');
                return;
            }

            clearInlineFeedback('assignFeedback');

            const rackSelect = document.getElementById('assignRackSelect');
            const assignDeviceId = document.getElementById('assignDeviceId');
            const assignDeviceName = document.getElementById('assignDeviceName');
            if (!rackSelect || !assignDeviceId || !assignDeviceName) return;

            assignDeviceId.value = String(device.id);
            assignDeviceName.textContent = `${device.name} (${device.serial_number})`;

            try {
                const racksResp = await apiCall('/racks/?page=1&page_size=100&sort_by=id&sort_order=asc&include_deleted=false');
                const racks = racksResp?.items || [];
                if (racks.length === 0) {
                    rackSelect.innerHTML = '';
                    setInlineFeedback('assignFeedback', 'Nema dostupnih rack-ova za dodelu.', 'warning');
                    return;
                }

                rackSelect.innerHTML = racks
                    .map(rack => `<option value="${rack.id}">${rack.name} (${rack.serial_number})</option>`)
                    .join('');

                new bootstrap.Modal(document.getElementById('assignDeviceModal')).show();
            } catch (e) {
                setInlineFeedback('assignFeedback', e.message, 'danger');
            }
        }

        async function confirmAssignDevice() {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }

            const deviceId = parseInt(document.getElementById('assignDeviceId')?.value || '0', 10);
            const rackId = parseInt(document.getElementById('assignRackSelect')?.value || '0', 10);
            if (!deviceId || !rackId) {
                setInlineFeedback('assignFeedback', 'Izaberite validan uređaj i rack.', 'warning');
                return;
            }

            clearInlineFeedback('assignFeedback');
            try {
                await apiCall(`/devices/${deviceId}/assign/${rackId}`, { method: 'POST' });
                bootstrap.Modal.getInstance(document.getElementById('assignDeviceModal'))?.hide();
                toast('Uređaj je uspešno dodeljen rack-u.', 'success');
                await loadAllData();
            } catch (e) {
                setInlineFeedback('assignFeedback', e.message, 'danger');
            }
        }

        async function unassignDevice(id) {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            if (!confirm('Da li želite da uklonite uređaj sa rack-a?')) return;

            try {
                await apiCall(`/devices/${id}/unassign`, { method: 'POST' });
                toast('Uređaj je uklonjen sa rack-a.', 'success');
                await loadAllData();
            } catch (e) {
                toast(e.message, 'danger');
            }
        }

        async function deleteRack(id) {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            if (!confirm('Da li ste sigurni da želite da arhivirate ovaj rack?')) return;

            try {
                const result = await apiCall(`/racks/${id}`, { method: 'DELETE' });
                if (result !== null) {
                    toast('Rack arhiviran!', 'success');
                    await loadAllData();
                }
            } catch (e) {
                if (e.status === 400) {
                    toast('Rack ima dodeljene uređaje i ne može biti arhiviran.', 'warning');
                    return;
                }
                toast(e.message, 'danger');
            }
        }

        async function restoreDevice(id) {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            if (!confirm('Da li želite da vratite ovaj uređaj iz arhive?')) return;

            try {
                const result = await apiCall(`/devices/${id}/restore`, { method: 'POST' });
                if (result !== null) {
                    toast('Uređaj vraćen iz arhive.', 'success');
                    await loadAllData();
                }
            } catch (e) {
                toast(e.message, 'danger');
            }
        }

        async function restoreRack(id) {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            if (!confirm('Da li želite da vratite ovaj rack iz arhive?')) return;

            try {
                const result = await apiCall(`/racks/${id}/restore`, { method: 'POST' });
                if (result !== null) {
                    toast('Rack vraćen iz arhive.', 'success');
                    await loadAllData();
                }
            } catch (e) {
                toast(e.message, 'danger');
            }
        }

        async function runBalancing() {
            try {
                const devicesResp = await apiCall('/devices/?page=1&page_size=100&sort_by=id&sort_order=asc');
                const racksResp = await apiCall('/racks/?page=1&page_size=100&sort_by=id&sort_order=asc');
                const allDevices = devicesResp?.items || [];
                const racks = racksResp?.items || [];
                const devices = allDevices;
                if (!racks || racks.length === 0) {
                    clearBalancingPlan();
                    toast('Nema dostupnih rack-ova za predlog.', 'warning');
                    return;
                }
                if (!devices || devices.length === 0) {
                    clearBalancingPlan();
                    document.getElementById('balancingResult').innerHTML = `
                        <div class="alert alert-info mb-0">
                            <i class="fas fa-info-circle"></i> Svi uređaji su već dodeljeni rack-ovima.
                        </div>
                    `;
                    return;
                }

                const deviceNameCount = {};
                devices.forEach(d => {
                    deviceNameCount[d.name] = (deviceNameCount[d.name] || 0) + 1;
                });

                function deviceLabelByIndex(index) {
                    const device = devices[index];
                    if (!device) return `#${index + 1}`;
                    if (deviceNameCount[device.name] > 1) return `${device.serial_number}`;
                    return `${device.name}`;
                }

                function rackLabelByIndex(index) {
                    const rack = racks[index];
                    if (!rack) return `#${index + 1}`;
                    return `${rack.name} (${rack.serial_number})`;
                }

                const balancingData = {
                    devices: devices.map(d => ({
                        name: d.name,
                        serial_number: d.serial_number,
                        units_occupied: d.units_occupied,
                        power_consumption: d.power_consumption
                    })),
                    racks: racks.map(r => ({
                        name: r.name,
                        serial_number: r.serial_number,
                        total_units: r.total_units,
                        max_power: r.max_power
                    }))
                };

                const result = await apiCall('/balance/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(balancingData)
                });

                if (result) {
                    latestBalancingPlan = result.assignments
                        .map(a => {
                            const device = devices[a.device_id];
                            const rack = racks[a.rack_id];
                            if (!device || !rack) return null;
                            return {
                                deviceId: device.id,
                                sourceRackId: device.rack_id,
                                rackId: rack.id,
                                deviceLabel: deviceLabelByIndex(a.device_id),
                                rackLabel: rackLabelByIndex(a.rack_id),
                            };
                        })
                        .filter(Boolean);
                    refreshBalancingApplyButton();

                    toast('Balansiranje uspešno završeno.', 'success');
                    document.getElementById('balancingResult').innerHTML = `
                        <div class="alert alert-success">
                            <h6><i class="fas fa-check-circle"></i> Balansiranje uspešno!</h6>
                            <p>Prikazan je idealan predlog kompletnog rasporeda (simulacija).</p>
                            <p>Predlog dodela: ${latestBalancingPlan.length}</p>
                            <p>Nedodeljeni uređaji: ${result.unassigned_devices.length}</p>
                            <ul class="mb-0">
                                ${result.assignments.map(a => `<li>Uređaj ${deviceLabelByIndex(a.device_id)} → Rack ${rackLabelByIndex(a.rack_id)}</li>`).join('')}
                            </ul>
                            <div class="d-flex flex-wrap gap-2 mt-3">
                                <button class="btn btn-success btn-sm ${isOperatorOrAdmin() ? '' : 'd-none'}" onclick="applyBalancingProposal()">
                                    <i class="fas fa-check"></i> Da, primeni ovako
                                </button>
                                <button class="btn btn-outline-secondary btn-sm" onclick="rejectBalancingProposal()">
                                    <i class="fas fa-xmark"></i> Ne, odustani
                                </button>
                            </div>
                        </div>
                    `;
                }
            } catch (e) {
                clearBalancingPlan();
                toast(e.message, 'danger');
                document.getElementById('balancingResult').innerHTML = `
                    <div class="alert alert-danger">${e.message}</div>
                `;
            }
        }

        async function applyBalancingProposal() {
            if (!isOperatorOrAdmin()) {
                toast('Nemate dozvolu za ovu akciju.', 'danger');
                return;
            }
            if (!latestBalancingPlan || latestBalancingPlan.length === 0) {
                toast('Nema aktivnog predloga za primenu.', 'warning');
                return;
            }
            if (!confirm(`Da li želite da primenite ${latestBalancingPlan.length} predloženih dodela?`)) return;

            let successCount = 0;
            let unchangedCount = 0;
            const failed = [];

            const moves = latestBalancingPlan.filter(a => a.sourceRackId !== a.rackId);

            // 1) Unassign only devices that must move from another rack.
            for (const assignment of moves) {
                if (assignment.sourceRackId == null) continue;
                try {
                    await apiCall(`/devices/${assignment.deviceId}/unassign`, {
                        method: 'POST',
                    });
                } catch (e) {
                    failed.push(`${assignment.deviceLabel} (unassign): ${e.message}`);
                }
            }

            // 2) Assign according to the proposed ideal layout.
            for (let index = 0; index < latestBalancingPlan.length; index += 1) {
                const assignment = latestBalancingPlan[index];
                if (assignment.sourceRackId === assignment.rackId) {
                    unchangedCount += 1;
                    continue;
                }
                try {
                    await apiCall(`/devices/${assignment.deviceId}/assign/${assignment.rackId}`, {
                        method: 'POST',
                        headers: {
                            'Idempotency-Key': `balancing-${assignment.deviceId}-${assignment.rackId}-${index}`,
                        },
                    });
                    successCount += 1;
                } catch (e) {
                    failed.push(`${assignment.deviceLabel} → ${assignment.rackLabel}: ${e.message}`);
                }
            }

            await loadAllData();

            if (failed.length === 0) {
                toast(`Predlog uspešno primenjen (${successCount} promena, ${unchangedCount} bez promene).`, 'success');
                document.getElementById('balancingResult').innerHTML = `
                    <div class="alert alert-success mb-0">
                        <h6><i class="fas fa-check-circle"></i> Predlog primenjen</h6>
                        <p class="mb-1">Uspešno primenjenih promena: ${successCount}</p>
                        <p class="mb-0">Već optimalno dodeljeni: ${unchangedCount}</p>
                    </div>
                `;
            } else {
                toast(`Delimična primena: ${successCount} uspešno, ${failed.length} neuspešno.`, 'warning');
                document.getElementById('balancingResult').innerHTML = `
                    <div class="alert alert-warning">
                        <h6><i class="fas fa-exclamation-triangle"></i> Delimična primena</h6>
                        <p>Uspešno: ${successCount}, bez promene: ${unchangedCount}, neuspešno: ${failed.length}</p>
                        <ul class="mb-0">${failed.map(item => `<li>${item}</li>`).join('')}</ul>
                    </div>
                `;
            }

            clearBalancingPlan();
        }

        async function runSeed() {
            if (!currentUser || currentUser.role !== 'admin') {
                toast('Samo admin može da pokrene seed.', 'danger');
                return;
            }

            try {
                const result = await apiCall('/seed', { method: 'POST' });
                if (result?.message) {
                    toast(result.message, 'success');
                } else {
                    toast('Seed je uspešno pokrenut.', 'success');
                }
                await loadAllData();
            } catch (e) {
                if (e.status === 409) {
                    toast('Baza je već seedovana.', 'warning');
                    await loadAllData();
                    return;
                }
                toast(e.message, 'danger');
            }
        }

        async function viewRackDetails(id) {
            const rack = await apiCall(`/racks/${id}`);
            if (rack) {
                const content = document.getElementById('rackDetailsContent');
                let details = `<div class="rack-details">`;
                details += `<h6 class="mb-3"><i class="fas fa-archive"></i> ${rack.name}</h6>`;
                details += `<div class="row mb-2">`;
                details += `<div class="col-sm-6"><strong>Serijski:</strong></div>`;
                details += `<div class="col-sm-6">${rack.serial_number}</div>`;
                details += `</div>`;
                details += `<div class="row mb-2">`;
                details += `<div class="col-sm-6"><strong>Jedinice:</strong></div>`;
                details += `<div class="col-sm-6">${rack.current_units}/${rack.total_units}U</div>`;
                details += `</div>`;
                details += `<div class="row mb-2">`;
                details += `<div class="col-sm-6"><strong>Snaga:</strong></div>`;
                details += `<div class="col-sm-6">${rack.current_power}/${rack.max_power}W</div>`;
                details += `</div>`;

                const utilization = rack.max_power > 0 ? ((rack.current_power / rack.max_power) * 100).toFixed(1) : 0;
                details += `<div class="row mb-3">`;
                details += `<div class="col-sm-6"><strong>Iskorišćenost:</strong></div>`;
                details += `<div class="col-sm-6">`;
                details += `<div class="progress" style="width: 100px;">`;
                details += `<div class="progress-bar bg-${utilization > 80 ? 'danger' : utilization > 60 ? 'warning' : 'success'}" style="width: ${utilization}%">
                    ${utilization}%
                </div></div></div>`;
                details += `</div>`;

                if (rack.devices && rack.devices.length > 0) {
                    details += '<h6 class="mt-3 mb-2"><i class="fas fa-desktop"></i> Uređaji u rack-u:</h6>';
                    details += '<ul class="list-group">';
                    rack.devices.forEach(device => {
                        details += `<li class="list-group-item d-flex justify-content-between align-items-center">`;
                        details += `${device.name}`;
                        details += `<span class="badge bg-primary rounded-pill">${device.power_consumption}W</span>`;
                        details += `</li>`;
                    });
                    details += '</ul>';
                } else {
                    details += '<div class="alert alert-info mt-3"><i class="fas fa-info-circle"></i> Ovaj rack nema dodeljene uređaje.</div>';
                }

                details += `</div>`;
                content.innerHTML = details;

                // Otvori modal
                const modal = new bootstrap.Modal(document.getElementById('viewRackModal'));
                modal.show();
            }
        }

        // Initialize chart
        let overviewChart;
        async function initChart() {
            const stats = await apiCall('/stats/');
            if (stats) {
                const ctx = document.getElementById('overviewChart').getContext('2d');
                if (overviewChart) overviewChart.destroy();

                overviewChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Iskorišćena Snaga', 'Dostupna Snaga'],
                        datasets: [{
                            data: [stats.total_power_consumed, stats.total_max_power - stats.total_power_consumed],
                            backgroundColor: ['#007bff', '#e9ecef'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
            }
        }

        // Load all data on page load
        async function loadAllData() {
            await loadStats();
            await loadDevices();
            await loadRacks();
            await initChart();
            if (currentUser && currentUser.role === 'admin') {
                await loadAuditLogs();
            }
        }

        window.onload = async function() {
            restoreDashboardFilters();

            document.getElementById('deviceSearch')?.addEventListener('input', () => {
                saveDeviceFilters();
                renderDevicesTable();
            });
            document.getElementById('deviceOnlyFree')?.addEventListener('change', () => {
                saveDeviceFilters();
                renderDevicesTable();
            });
            document.getElementById('deviceIncludeArchived')?.addEventListener('change', async () => {
                if (document.getElementById('deviceIncludeArchived')?.checked === true) {
                    const onlyFreeInput = document.getElementById('deviceOnlyFree');
                    const searchInput = document.getElementById('deviceSearch');
                    if (onlyFreeInput) onlyFreeInput.checked = false;
                    if (searchInput) searchInput.value = '';
                }
                saveDeviceFilters();
                await loadDevices();
            });
            document.getElementById('rackSearch')?.addEventListener('input', () => {
                saveRackFilters();
                renderRacksTable();
            });
            document.getElementById('rackLoadFilter')?.addEventListener('change', () => {
                saveRackFilters();
                renderRacksTable();
            });
            document.getElementById('rackIncludeArchived')?.addEventListener('change', async () => {
                if (document.getElementById('rackIncludeArchived')?.checked === true) {
                    const loadFilterInput = document.getElementById('rackLoadFilter');
                    const searchInput = document.getElementById('rackSearch');
                    if (loadFilterInput) loadFilterInput.value = 'all';
                    if (searchInput) searchInput.value = '';
                }
                saveRackFilters();
                await loadRacks();
            });

            const restored = await ensureSession();
            if (restored) {
                await loadAllData();
            }

            // Auto refresh every 30 seconds only when logged in
            setInterval(async () => {
                if (!authToken) return;
                await loadAllData();
            }, 30000);
        };
    </script>
</body>
</html>
    """