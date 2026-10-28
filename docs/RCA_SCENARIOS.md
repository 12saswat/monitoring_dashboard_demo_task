# Failure Simulation & Root Cause Analysis (RCA) Scenarios

This guide details the 4 failure scenarios implemented in the FastAPI application, demonstrating failure detection, automated alerting, and root cause diagnostic output.

---

## Scenario 1: Invalid API Authentication

### Objective
Verify that missing or tampered authentication credentials are detected immediately, logged as HTTP 401, and trigger a security warning alert.

### Test Command
```bash
curl -i http://localhost:8000/secure-data \
     -H "Authorization: Bearer invalid-tampered-token"
```

### Observed Behavior
- **HTTP Status Code**: `401 Unauthorized`
- **Response Body**:
  ```json
  {"detail": "Invalid authentication token. Verification failed."}
  ```
- **Monitoring Detection**:
  - Telemetry logs status code `401` with `client_ip` and duration.
  - Alert rule `AUTH_FAILURE_DETECTED` is evaluated.
- **Root Cause Analysis (RCA)**:
  - **Summary**: Client request lacked valid authentication credentials. The Authorization header was missing or contained an invalid token.
  - **Remediation**:
    1. Verify client sends valid `Authorization: Bearer sentinel-secure-token-2026` (or `AUTH_DEMO_TOKEN` from `.env`).
    2. Check token expiration and signature.
    3. Audit IP logs for brute-force attempts.

---

## Scenario 2: API Timeout / High Latency SLA Breach

### Objective
Demonstrate detection of high response latency exceeding the 3.0-second service level agreement (SLA) threshold.

### Test Command
```bash
curl -i "http://localhost:8000/simulate-timeout?delay_seconds=3.5"
```

### Observed Behavior
- **HTTP Status Code**: `200 OK` (delayed response)
- **Measured Duration**: `3520 ms` (exceeds 3000ms SLA)
- **Monitoring Detection**:
  - Middleware measures high-resolution latency with `time.perf_counter()`.
  - Alert rule `LATENCY_SLA_BREACH` triggers immediately.
  - P95 latency metric spikes on the live dashboard.
- **Root Cause Analysis (RCA)**:
  - **Summary**: Response time of 3520ms breached the 3000ms SLA threshold.
  - **Technical Cause**: Worker thread blocking or slow I/O loop.
  - **Remediation**:
    1. Ensure no synchronous blocking operations (e.g. `time.sleep`) block FastAPI's async event loop.
    2. Add database indexes to slow queries.
    3. Offload compute-heavy processing to async task queues (Celery/RQ).

---

## Scenario 3: Server Error (HTTP 500)

### Objective
Demonstrate automated handling of unhandled server exceptions, capturing stack traces, notifying on-call engineers, and generating instant diagnostic root causes.

### Test Command
```bash
curl -i "http://localhost:8000/simulate-error?error_kind=math"
```

### Observed Behavior
- **HTTP Status Code**: `500 Internal Server Error`
- **Response Body**:
  ```json
  {
    "error": "InternalServerError",
    "message": "An unexpected error occurred processing your request.",
    "request_id": "49613080-dcb1-46bc-bec9-289e0559ee52",
    "rca_available": true
  }
  ```
- **Monitoring Detection**:
  - Middleware intercepts exception without crashing the uvicorn process.
  - Captured Exception: `ZeroDivisionError: division by zero`.
  - Full Python traceback recorded in SQLite `api_request_logs`.
  - Alert rule `HTTP_500_INTERNAL_SERVER_ERROR` fires `CRITICAL` alert.
- **Root Cause Analysis (RCA)**:
  - **Summary**: Unhandled server exception during `GET /simulate-error`. Triggered by arithmetic division by zero.
  - **Remediation**:
    1. Guard denominators with `if denominator != 0:`.
    2. Add input validation rules via Pydantic schemas.
    3. Implement safe fallback responses.

---

## Scenario 4: Rate Limit Exceeded (HTTP 429)

### Objective
Demonstrate API rate limiting, client request throttling, and defensive protection against traffic spikes.

### Test Command
```bash
curl -i "http://localhost:8000/simulate-rate-limit?force_breach=true"
```

### Observed Behavior
- **HTTP Status Code**: `429 Too Many Requests`
- **Response Headers**: `Retry-After: 10`
- **Response Body**:
  ```json
  {"detail": "Rate limit exceeded: 10 requests per 10s quota exhausted."}
  ```
- **Monitoring Detection**:
  - Telemetry registers 429 status code.
  - Alert rule `RATE_LIMIT_EXCEEDED` fires warning alert.
  - Status distribution chart reflects 4xx error percentage rise.
- **Root Cause Analysis (RCA)**:
  - **Summary**: Client exceeded sliding window quota (10 requests per 10-second window).
  - **Remediation**:
    1. Instruct API consumers to parse `Retry-After` header.
    2. Implement exponential backoff and jitter in client applications.
    3. Upgrade high-volume partners to premium rate tiers in API gateway.

Natural window (without `force_breach`):
```bash
for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/simulate-rate-limit?force_breach=false; done
```

---

## Scenario 5: Increased Failure Rate

### Test Command
```bash
for i in $(seq 1 8); do curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/simulate-error?error_kind=math"; done
```

### Observed Behavior
- **Alert**: `INCREASED_FAILURE_RATE` (WARNING) once the rolling window error percentage crosses `ALERT_ERROR_RATE_PERCENT`.

---

## Scenario 6: Service Health Failure

### Test Command
```bash
curl -i http://localhost:8000/simulate-health-failure
```

### Observed Behavior
- **HTTP Status Code**: `503 Service Unavailable`
- **Alert**: `SERVICE_HEALTH_FAILURE` (CRITICAL) plus `API_DOWNTIME` because a failed health probe is treated as an outage.

---

## Scenario 7: API Downtime

### Test Command
```bash
curl -i http://localhost:8000/simulate-downtime
```

### Observed Behavior
- **HTTP Status Code**: `503 Service Unavailable`
- **Alert**: `API_DOWNTIME` (CRITICAL) and `SERVICE_HEALTH_FAILURE` (CRITICAL)
- **Call channel**: live `CALL_WEBHOOK_URL` if configured, otherwise simulated pager log.
