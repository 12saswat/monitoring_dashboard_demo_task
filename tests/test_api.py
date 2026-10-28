import pytest
from starlette.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.alert_service import AlertService
from app.services.metrics_service import MetricsService
from app.middleware.rate_limiter import rate_limiter

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_alert_state():
    AlertService._cooldown_cache.clear()
    yield


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["database"]["status"] == "healthy"
    assert "cpu_percent" in data["system"]


def test_get_users():
    response = client.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert "email" in data["data"][0]


def test_get_products():
    response = client.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert "sku" in data["data"][0]


def test_unauthorized_access():
    r_unauth = client.get("/secure-data")
    assert r_unauth.status_code == 401

    r_auth = client.get("/secure-data", headers={"Authorization": f"Bearer {settings.auth_demo_token}"})
    assert r_auth.status_code == 200
    assert r_auth.json()["status"] == "authenticated"

    stats = client.get("/api/monitoring/stats").json()
    rules = [a["rule_name"] for a in stats["recent_alerts"]]
    assert "AUTH_FAILURE_DETECTED" in rules


def test_latency_sla_breach(monkeypatch):
    monkeypatch.setattr(settings, "latency_threshold_sec", 0.05)
    response = client.get("/simulate-timeout?delay_seconds=0.12")
    assert response.status_code == 200
    assert response.json()["status"] == "completed_with_latency"
    assert float(response.headers["X-Response-Time-Ms"]) >= 50

    stats = client.get("/api/monitoring/stats").json()
    rules = [a["rule_name"] for a in stats["recent_alerts"]]
    assert "LATENCY_SLA_BREACH" in rules


def test_server_error():
    response = client.get("/simulate-error?error_kind=math")
    assert response.status_code == 500
    assert response.json()["error"] == "InternalServerError"

    rca = client.get(f"/api/monitoring/rca/{response.headers['X-Request-ID']}").json()
    assert rca["analysis"]["rule_name"] == "HTTP_500_INTERNAL_SERVER_ERROR"
    assert rca["error_type"] == "ZeroDivisionError"


def test_rate_limit_exceeded():
    rate_limiter.reset()
    response = client.get("/simulate-rate-limit?force_breach=true")
    assert response.status_code == 429
    assert "Retry-After" in response.headers

    stats = client.get("/api/monitoring/stats").json()
    rules = [a["rule_name"] for a in stats["recent_alerts"]]
    assert "RATE_LIMIT_EXCEEDED" in rules


def test_rate_limit_sliding_window():
    rate_limiter.reset()
    old_win = rate_limiter.window_seconds
    rate_limiter.window_seconds = 60
    try:
        allowed = 0
        blocked = 0
        for _ in range(12):
            r = client.get("/simulate-rate-limit?force_breach=false")
            if r.status_code == 200:
                allowed += 1
            elif r.status_code == 429:
                blocked += 1
        assert allowed == 10
        assert blocked >= 1
    finally:
        rate_limiter.window_seconds = old_win
        rate_limiter.reset()


def test_service_health_failure_and_downtime():
    health = client.get("/simulate-health-failure")
    assert health.status_code == 503
    down = client.get("/simulate-downtime")
    assert down.status_code == 503

    stats = client.get("/api/monitoring/stats").json()
    rules = [a["rule_name"] for a in stats["recent_alerts"]]
    assert "SERVICE_HEALTH_FAILURE" in rules
    assert "API_DOWNTIME" in rules


def test_increased_failure_rate(monkeypatch):
    monkeypatch.setattr(settings, "sliding_window_size", 5)
    monkeypatch.setattr(settings, "error_rate_threshold_pct", 40.0)
    MetricsService._recent_requests.clear()
    AlertService._cooldown_cache.clear()
    for _ in range(3):
        client.get("/simulate-error?error_kind=math")
    for _ in range(2):
        client.get("/users")
    stats = client.get("/api/monitoring/stats").json()
    rules = [a["rule_name"] for a in stats["recent_alerts"]]
    assert "INCREASED_FAILURE_RATE" in rules


def test_monitoring_stats():
    response = client.get("/api/monitoring/stats")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_pct" in data
    assert "total_requests" in data
    assert "recent_logs" in data


def test_prometheus_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "fastapi_requests_total" in body
    assert "fastapi_system_disk_percent" in body
    assert "fastapi_error_rate_percent" in body


def test_dashboard_page():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "FastAPI API Sentinel" in response.text


def test_root_redirect():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/dashboard"
