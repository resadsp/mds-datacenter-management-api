from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.database import engine
from app import models
from app.routers import devices, racks, balancing, stats, seed

# Kreiramo tabele u bazi ako ne postoje
models.Base.metadata.create_all(bind=engine)

# Inicijalizacija FastAPI aplikacije sa osnovnim informacijama
app = FastAPI(
    title="Data Center Management API",
    description="API za upravljanje uređajima i rack-ovima u data centru, praćenje potrošnje energije i predloge balansiranog rasporeda.",
    version="1.0.0"
)

# Uključujemo rutere sa prefiksom /api/v1 za organizovanu strukturu API-ja
app.include_router(devices.router, prefix="/api/v1", tags=["Uređaji"])
app.include_router(racks.router, prefix="/api/v1", tags=["Rack-ovi"])
app.include_router(balancing.router, prefix="/api/v1", tags=["Balansiranje"])
app.include_router(stats.router, prefix="/api/v1", tags=["Statistike"])
app.include_router(seed.router, prefix="/api/v1")


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "zdravo"}

# Glavni dashboard na root endpoint-u
@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    return """
<!DOCTYPE html>
<html lang="sr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Data Center Management System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .navbar { background: rgba(255,255,255,0.95) !important; backdrop-filter: blur(10px); }
        .card { border: none; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); transition: transform 0.3s; }
        .card:hover { transform: translateY(-5px); }
        .btn-primary { background: linear-gradient(45deg, #007bff, #0056b3); border: none; }
        .btn-success { background: linear-gradient(45deg, #28a745, #1e7e34); border: none; }
        .btn-danger { background: linear-gradient(45deg, #dc3545, #bd2130); border: none; }
        .btn-warning { background: linear-gradient(45deg, #ffc107, #e0a800); border: none; }
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
            box-shadow: 0 8px 24px rgba(0,0,0,.12);
            animation: slideIn .18s ease-out;
        }

        .inline-feedback {
            margin-top: 10px;
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
                    <i class="fas fa-circle text-success"></i> Sistem Aktivan
                </span>
                <button class="btn btn-outline-primary btn-sm" onclick="location.reload()">
                    <i class="fas fa-sync-alt"></i> Osveži
                </button>
            </div>
        </div>
    </nav>

    <div class="container">
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
                    <i class="fas fa-archive fa-2x text-success mb-2"></i>
                    <h4 id="totalRacks">-</h4>
                    <p class="text-muted mb-0">Ukupno Rack-ova</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <i class="fas fa-bolt fa-2x text-warning mb-2"></i>
                    <h4 id="totalPower">-</h4>
                    <p class="text-muted mb-0">Potrošnja (W)</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <i class="fas fa-chart-pie fa-2x text-info mb-2"></i>
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
                        <button class="btn btn-light btn-sm" data-bs-toggle="modal" data-bs-target="#addDeviceModal">
                            <i class="fas fa-plus"></i> Dodaj
                        </button>
                    </div>
                    <div class="card-body">
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
                        <button class="btn btn-light btn-sm" data-bs-toggle="modal" data-bs-target="#addRackModal">
                            <i class="fas fa-plus"></i> Dodaj
                        </button>
                    </div>
                    <div class="card-body">
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

        <!-- Balansiranje -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-warning text-dark">
                        <h5 class="mb-0"><i class="fas fa-balance-scale"></i> Inteligentno Balansiranje</h5>
                    </div>
                    <div class="card-body">
                        <p class="mb-3">Algoritam automatski balansira uređaje po rack-ovima za optimalnu iskorišćenost energije.</p>
                        <button class="btn btn-warning btn-lg" onclick="runBalancing()">
                            <i class="fas fa-magic"></i> Pokreni Balansiranje
                        </button>
                        <div id="balancingResult" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modali za dodavanje -->
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
    <div class="floating-btn">
        <button class="btn btn-primary btn-lg rounded-circle" data-bs-toggle="modal" data-bs-target="#addDeviceModal">
            <i class="fas fa-plus"></i>
        </button>
    </div>

    <div id="floatingAlerts" class="floating-alerts"></div>

    <div id="toastStack" class="toast-stack" aria-live="polite" aria-atomic="true"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const API_BASE = "/api/v1";

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

        async function apiCall(endpoint, options = {}) {
            const response = await fetch(`${API_BASE}${endpoint}`, options);
            const ct = response.headers.get("content-type") || "";
            const payload = ct.includes("application/json") ? await response.json() : await response.text();

            if (!response.ok) {
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
            const devices = await apiCall('/devices/');
            if (devices) {
                const tbody = document.querySelector('#devicesTable tbody');
                tbody.innerHTML = devices.map(device => `
                    <tr>
                        <td>${device.name}</td>
                        <td>${device.serial_number}</td>
                        <td>${device.units_occupied}U</td>
                        <td>${device.power_consumption}W</td>
                        <td>
                            <span class="badge bg-${device.rack_id ? 'success' : 'secondary'}">
                                ${device.rack_id ? 'Dodeljen' : 'Slobodan'}
                            </span>
                        </td>
                        <td>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteDevice(${device.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            }
        }

        async function loadRacks() {
            const racks = await apiCall('/racks/');
            if (racks) {
                const tbody = document.querySelector('#racksTable tbody');
                tbody.innerHTML = racks.map(rack => {
                    const utilization = rack.max_power > 0 ? ((rack.current_power / rack.max_power) * 100).toFixed(1) : 0;
                    const statusClass = utilization > 80 ? 'danger' : utilization > 60 ? 'warning' : 'success';
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
                                <span class="badge bg-${statusClass}">
                                    ${utilization > 80 ? 'Visoko' : utilization > 60 ? 'Srednje' : 'Nisko'}
                                </span>
                            </td>
                            <td>
                                <button class="btn btn-sm btn-outline-info" onclick="viewRackDetails(${rack.id})">
                                    <i class="fas fa-eye"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // Add functions
        async function addDevice() {
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

        async function runBalancing() {
            try {
                const devices = await apiCall('/devices/');
                const racks = await apiCall('/racks/');
                if (!devices || !racks) return;

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
                    toast('Balansiranje uspešno završeno.', 'success');
                    document.getElementById('balancingResult').innerHTML = `
                        <div class="alert alert-success">
                            <h6><i class="fas fa-check-circle"></i> Balansiranje uspešno!</h6>
                            <p>Dodeljeno uređaja: ${result.assignments.length}</p>
                            <p>Nedodeljeni uređaji: ${result.unassigned_devices.length}</p>
                            <ul class="mb-0">
                                ${result.assignments.map(a => `<li>Uređaj ${a.device_id + 1} → Rack ${a.rack_id + 1}</li>`).join('')}
                            </ul>
                        </div>
                    `;
                }
            } catch (e) {
                toast(e.message, 'danger');
                document.getElementById('balancingResult').innerHTML = `
                    <div class="alert alert-danger">${e.message}</div>
                `;
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
        window.onload = function() {
            loadStats();
            loadDevices();
            loadRacks();
            initChart();

            // Auto refresh every 30 seconds
            setInterval(() => {
                loadStats();
                loadDevices();
                loadRacks();
                initChart();
            }, 30000);
        };
    </script>
</body>
</html>
    """