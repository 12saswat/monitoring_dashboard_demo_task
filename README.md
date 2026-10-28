# FastAPI API Monitoring, Alerting & Root Cause Analysis Platform

An enterprise-ready API monitoring, performance tracking, alerting, and automated Root Cause Analysis (RCA) platform built around a high-performance **FastAPI** service with a persistent **SQLite** telemetry store and **Prometheus** metrics exporter.

![Dashboard Preview](docs/images/dashboard_preview.jpg)

---

## 🎯 Project Objectives & Highlights

- **FastAPI Sample Application**: High-performance REST service providing `/health`, `/users`, `/products`, `/secure-data`, and scenario simulation endpoints.
- **SQLite Persistence**: High-throughput telemetry and incident logging configured with Write-Ahead Logging (`WAL` mode) and busy timeouts for safe multi-threaded concurrency.
- **Real-time Observability Dashboard**: Sleek, dark-themed operations dashboard with live KPI cards, time-series charts (Chart.js), HTTP status distribution, and an interactive **Failure Simulation Lab**.
- **Automated Root Cause Analysis (RCA)**: Instant diagnostic engine that classifies failure signatures, extracts Python stack traces, and produces actionable 3-step runbooks.
- **Multi-Channel Alerting**: Instant notification dispatchers supporting Slack (Block Kit JSON), Email (HTML email body), and on-call escalation calls for Critical incidents.
- **Industry Standard Metrics**: Native Prometheus exporter at `/metrics` for Grafana, Datadog, or New Relic integration.

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend API** | FastAPI (Python 3.10+) | Asynchronous REST service & telemetry middleware |
| **Database** | SQLite + SQLAlchemy 2.0 | Application entities (`users`, `products`) & telemetry logs (`WAL` mode) |
| **Metrics Exporter** | Prometheus Client | Standard `/metrics` scrape target (Counters, Gauges, Histograms) |
| **Host Telemetry** | `psutil` | System CPU, RAM, Disk, and SQLite latency monitoring |
| **Frontend UI** | HTML5, Vanilla CSS, Chart.js | Real-time monitoring dashboard served directly by FastAPI |
| **Testing** | Pytest, HTTPX | Automated unit, integration, and failure scenario test suites |

---

## 🚀 Quickstart Guide

### 1. Clone & Set Up Virtual Environment

```bash
# Navigate to project directory
cd FASTAPI_API_Monitoring_Dashboard_Demo_Task

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Defaults work out of the box with zero external configuration required).*

### 3. Launch the Application

```bash
python run.py
```
The server will start at `http://localhost:8000`.

- 📊 **Monitoring Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- 📖 **Swagger OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 📈 **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- 🏥 **Health Check API**: [http://localhost:8000/health](http://localhost:8000/health)

Optional Prometheus + Grafana (with the API already running):

```bash
docker compose up -d
```

- Grafana: [http://localhost:3000](http://localhost:3000) (admin/admin) — provisioned **FastAPI API Sentinel** dashboard
- Prometheus: [http://localhost:9090](http://localhost:9090)

---

## 🧪 Automated Testing & Verification

### Run Pytest Suite
```bash
python -m pytest -v
```
**Result**: 14 tests covering health, users, products, auth, timeout, server error, sliding-window rate limit, service availability, metrics exporter, and dashboard.

### Run End-to-End Simulation Script
```bash
python scripts/test_all_scenarios.py
```
This script tests failure conditions against the server to verify status code handling, SQLite persistence, and diagnostic generation.

### Run Continuous Traffic Generator
```bash
python scripts/generate_traffic.py
```
Dispatches realistic organic traffic (90% success, 10% edge cases) to animate the live dashboard charts.

---

## 🔍 Root Cause Analysis (RCA) & Failure Scenarios

![RCA Modal Preview](docs/images/rca_modal_preview.jpg)

### Scenario 1: Invalid API Authentication
- **Endpoint**: `GET /secure-data`
- **Trigger**: Missing or invalid `Authorization: Bearer <token>`
- **Detection**: Returns `HTTP 401 Unauthorized`
- **Alert**: `AUTH_FAILURE_DETECTED` (WARNING)
- **RCA Diagnostic**: Identifies rejected token and captures client IP for security audit.

### Scenario 2: API Timeout (> 3.0s SLA Breach)
- **Endpoint**: `GET /simulate-timeout?delay_seconds=3.5`
- **Trigger**: Artificial delay exceeding 3.0-second SLA
- **Detection**: Latency measured via `time.perf_counter()`
- **Alert**: `LATENCY_SLA_BREACH` (WARNING)
- **RCA Diagnostic**: Pinpoints potential blocking I/O or compute loop.

### Scenario 3: Server Error (HTTP 500)
- **Endpoint**: `GET /simulate-error?error_kind=math`
- **Trigger**: Unhandled `ZeroDivisionError`
- **Detection**: Caught by telemetry middleware; returns structured 500 JSON
- **Alert**: `HTTP_500_INTERNAL_SERVER_ERROR` (CRITICAL)
- **RCA Diagnostic**: Captures complete Python traceback and suggests denominator validation guards.

### Scenario 4: Rate Limit Exceeded (HTTP 429)
- **Endpoint**: `GET /simulate-rate-limit?force_breach=true`
- **Trigger**: Burst traffic exceeding 10 requests per 10-second sliding window
- **Detection**: Returns `HTTP 429 Too Many Requests` with `Retry-After: 10`
- **Alert**: `RATE_LIMIT_EXCEEDED` (WARNING)
- **RCA Diagnostic**: Logs client IP and recommends exponential backoff.

---

## 🔔 Alert Notification Proofs

### 1. Slack Block Kit Payload
```json
{
  "attachments": [{
    "color": "#e02424",
    "blocks": [
      {"type": "header", "text": {"type": "plain_text", "text": "🚨 [CRITICAL] Critical 500 Error on GET /simulate-error"}},
      {"type": "section", "fields": [
        {"type": "mrkdwn", "text": "*Alert ID:*\n`ALT-49613080`"},
        {"type": "mrkdwn", "text": "*Severity:*\n*CRITICAL*"}
      ]},
      {"type": "section", "text": {"type": "mrkdwn", "text": "*Root Cause:*\nUnhandled ZeroDivisionError in calculation pipeline"}}
    ]
  }]
}
```

### 2. Email HTML Notification
Formatted with alert severity banner, failure details, automated RCA summary, and direct link to runbook remediation.

### 3. Audio/Pager Escalation
Critical alerts POST to `CALL_WEBHOOK_URL` when set; otherwise they record a simulated on-call page in logs and on the alert inspect modal.

---

## 📚 Technical Documentation Index

- [System Architecture & Dataflow](docs/ARCHITECTURE.md)
- [Alerting Rules & Notification Setup](docs/ALERTING_RULES.md)
- [Root Cause Analysis (RCA) Deep-Dive](docs/RCA_SCENARIOS.md)
- [Operational Runbook & Troubleshooting](docs/RUNBOOK.md)

---

## 📋 Definition of Done Checklist

- [x] FastAPI sample API created and running with SQLite database.
- [x] API monitoring middleware configured for latency, status codes, and server health.
- [x] Web dashboard displays uptime %, average response time, request counters, error trends, and alerts.
- [x] Alerts configured for downtime, latency > 3s, 500 errors, auth failures, rate limits, increased failure rate, and service health failure.
- [x] All 4 failure scenarios simulated and successfully detected.
- [x] Root Cause Analysis engine captures stack traces, diagnoses causes, and provides runbook steps.
- [x] Comprehensive documentation provided (Architecture, Alerting, RCA, Runbook, README).
