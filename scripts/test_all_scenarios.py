import sys
import time
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def log_step(title):
    print(f"\n{'='*60}\n>> {title}\n{'='*60}")

def run_tests():
    print(f"Connecting to FastAPI Monitoring Target: {BASE_URL}")
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 0. Health check
    log_step("Verifying Base Service Health (/health)")
    try:
        r = client.get("/health")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        assert r.status_code == 200, "Health check failed"
    except Exception as e:
        print(f"Failed to reach server at {BASE_URL}. Ensure 'python run.py' is running!")
        sys.exit(1)

    log_step("Seeding Initial Requests (/users, /products)")
    for _ in range(5):
        client.get("/users")
        client.get("/products")
    print("Dispatched initial requests.")

    log_step("Testing Authentication (/secure-data)")
    r1 = client.get("/secure-data", headers={"Authorization": "Bearer invalid_unauthorized_token"})
    print(f"HTTP Status: {r1.status_code} (Expected 401)")
    print(f"Response: {r1.json()}")
    assert r1.status_code == 401, "Auth test failed to return 401"
    print("Unauthorized access handled.")

    log_step("Testing Timeout Simulation (/simulate-timeout)")
    start_t = time.perf_counter()
    r2 = client.get("/simulate-timeout", params={"delay_seconds": 3.2})
    elapsed = round(time.perf_counter() - start_t, 2)
    print(f"HTTP Status: {r2.status_code}")
    print(f"Duration: {elapsed}s (Expected > 3.0s)")
    print(f"Response: {r2.json()}")
    assert elapsed >= 3.0, "Latency was lower than 3.0s"
    print("Timeout test passed.")

    log_step("Testing Server Error Simulation (/simulate-error)")
    r3 = client.get("/simulate-error", params={"error_kind": "math"})
    print(f"HTTP Status: {r3.status_code} (Expected 500)")
    print(f"Response: {r3.json()}")
    assert r3.status_code == 500, "Error test failed to return 500"
    print("500 internal server error handled.")

    log_step("Testing Rate Limit (/simulate-rate-limit)")
    r4 = client.get("/simulate-rate-limit", params={"force_breach": True})
    print(f"HTTP Status: {r4.status_code} (Expected 429)")
    print(f"Response: {r4.json()}")
    print(f"Headers: Retry-After = {r4.headers.get('Retry-After')}")
    assert r4.status_code == 429, "Rate limit test failed to return 429"
    print("429 rate limit caught.")

    log_step("Testing Health Failure and Downtime (/simulate-health-failure, /simulate-downtime)")
    r5 = client.get("/simulate-health-failure")
    r6 = client.get("/simulate-downtime")
    print(f"Health failure: {r5.status_code}  Downtime: {r6.status_code} (Expected 503)")
    assert r5.status_code == 503 and r6.status_code == 503
    for _ in range(6):
        client.get("/simulate-error", params={"error_kind": "math"})
    print("Health and downtime tests dispatched.")

    log_step("Validating Telemetry & Stats (/api/monitoring/stats)")
    time.sleep(1)
    stats_resp = client.get("/api/monitoring/stats")
    stats = stats_resp.json()

    print(f"Total Requests: {stats['total_requests']}")
    print(f"Failed Requests: {stats['failed_requests']}")
    print(f"Calculated Error Rate: {stats['error_rate']}%")
    print(f"Active Alerts: {stats['active_alerts_count']}")
    print(f"Service Status: {stats['service_status']}")

    assert stats["total_requests"] > 0, "No telemetry was logged"
    assert stats["failed_requests"] >= 4, "Failures were not captured"
    assert len(stats["recent_alerts"]) > 0, "No alerts were generated"

    log_step("Validating Prometheus Metrics Export (/metrics)")
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "fastapi_requests_total" in metrics_resp.text
    assert "fastapi_request_duration_seconds" in metrics_resp.text
    print("Prometheus metrics verified.")

    print("\n" + "="*60)
    print("All checks completed successfully.")
    print("="*60)

if __name__ == "__main__":
    run_tests()
