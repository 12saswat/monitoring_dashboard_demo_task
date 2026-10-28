# Alerting Rules & Notification Configuration

This document specifies the alerting policies, threshold conditions, severity definitions, and notification dispatch mechanisms implemented in FastAPI API Sentinel.

## Alert Severity Levels

| Severity | Color | Trigger Condition | Notification Channels | Escalation SLA |
| :--- | :--- | :--- | :--- | :--- |
| **CRITICAL** | Red (`#ef4444`) | HTTP 500 unhandled exceptions, database disconnect, service outage | Slack, Email, Simulated Call Pager | Immediate (< 5 min) |
| **WARNING** | Amber (`#f59e0b`) | Latency > 3.0s, Rate limit throttling (429), Auth failures (401) | Slack, Email | Within 30 minutes |
| **INFO** | Blue (`#3b82f6`) | Informational health status changes, alert resolutions | Dashboard event log | Non-urgent |

---

## Active Alert Rules

### 1. HTTP 500 Unhandled Server Error
- **Rule ID**: `HTTP_500_INTERNAL_SERVER_ERROR`
- **Severity**: `CRITICAL`
- **Trigger**: Any endpoint yielding status code $\ge 500$ or throwing an unhandled exception.
- **RCA Automation**: Extracts exception type (e.g., `ZeroDivisionError`, `OperationalError`), failing function name, and traceback frame.
- **Action Items**:
  1. Inspect the traceback stack frame where the exception was raised.
  2. Validate incoming request payload types with Pydantic schemas.
  3. Ensure denominators are guarded (`if denominator != 0`).

### 2. Response Time SLA Breach (> 3.0 Seconds)
- **Rule ID**: `LATENCY_SLA_BREACH`
- **Severity**: `WARNING`
- **Trigger**: Any endpoint response time $\ge 3000\text{ ms}$.
- **RCA Automation**: Compares observed latency against the 3000ms SLA, identifies suspected blocking I/O or heavy computation.
- **Action Items**:
  1. Inspect async event loop for un-awaited blocking synchronous calls.
  2. Add indexes to SQLite database tables.
  3. Offload long batch jobs to background worker queues.

### 3. Invalid Authentication Attempts
- **Rule ID**: `AUTH_FAILURE_DETECTED`
- **Severity**: `WARNING`
- **Trigger**: Client requests to protected routes returning HTTP 401.
- **RCA Automation**: Detects missing or rejected `Authorization: Bearer <token>` headers, tracks originating client IP.
- **Action Items**:
  1. Verify client is providing correct credentials.
  2. Check for token expiration or credential rotation.
  3. Monitor client IP for brute force or credential stuffing attacks.

### 4. Rate Limit Throttling (HTTP 429)
- **Rule ID**: `RATE_LIMIT_EXCEEDED`
- **Severity**: `WARNING`
- **Trigger**: Client exceeding rate limit quota (10 requests per 10-second sliding window) on `GET /simulate-rate-limit`.
- **RCA Automation**: Identifies client IP and checks sliding window bucket.
- **Action Items**:
  1. Instruct client to parse and respect `Retry-After` header.
  2. Add exponential backoff and jitter in API consumers.

### 5. Increased Failure Rate
- **Rule ID**: `INCREASED_FAILURE_RATE`
- **Severity**: `WARNING`
- **Trigger**: Share of 4xx/5xx responses in the last `ALERT_WINDOW_SIZE` requests (default 20) is at or above `ALERT_ERROR_RATE_PERCENT` (default 20%).
- **RCA Automation**: Reports window size, error percentage, and recommended correlation steps.
- **Action Items**:
  1. Inspect recent telemetry for a dominant status code.
  2. Correlate with deploys, auth storms, or timeout bursts.
  3. Pause load tests if they are the source of the spike.

### 6. Service Health Failure
- **Rule ID**: `SERVICE_HEALTH_FAILURE`
- **Severity**: `CRITICAL`
- **Trigger**: HTTP 503 from `/health`, `/simulate-health-failure`, or host CPU/RAM above `ALERT_CPU_PERCENT` / `ALERT_MEMORY_PERCENT`; SQLite ping failure.
- **Channels**: Slack, Email, Call/pager (live `CALL_WEBHOOK_URL` or simulated).
- **Action Items**:
  1. Check CPU, RAM, and disk on the dashboard banner.
  2. Verify SQLite WAL files and `PRAGMA busy_timeout`.
  3. Restore `/health` to HTTP 200.

### 7. API Downtime
- **Rule ID**: `API_DOWNTIME`
- **Severity**: `CRITICAL`
- **Trigger**: HTTP 503 from `/simulate-downtime` or a failed health probe (`/health`, `/simulate-health-failure`).
- **Channels**: Slack, Email, Call/pager.
- **Action Items**:
  1. Confirm `python run.py` / uvicorn is running.
  2. Restore database connectivity.
  3. Re-run `curl http://localhost:8000/health`.

---

## Notification Dispatch Channels

### 1. Slack Webhook Integration
When an alert fires, a Slack Block Kit payload is generated:
```json
{
  "attachments": [{
    "color": "#e02424",
    "blocks": [
      {"type": "header", "text": {"type": "plain_text", "text": "🚨 [CRITICAL] Critical 500 Error on GET /simulate-error"}},
      {"type": "section", "fields": [
        {"type": "mrkdwn", "text": "*Alert ID:*\n`ALT-A84F2B01`"},
        {"type": "mrkdwn", "text": "*Severity:*\n*CRITICAL*"}
      ]},
      {"type": "section", "text": {"type": "mrkdwn", "text": "*Root Cause Analysis:*\nZeroDivisionError in calculate_analytics()"}}
    ]
  }]
}
```

### 2. Email Notifications (HTML)
Sends a responsive HTML alert containing:
- Incident Title & Severity Badge
- Error Message & Root Cause Analysis breakdown
- Direct link to Runbook and remediation steps

### 3. Phone / Call Escalation
For `CRITICAL` severity alerts:
- If `CALL_WEBHOOK_URL` is set, a JSON pager payload is POSTed (Twilio Function, n8n, or similar).
- Otherwise a simulated on-call page is written to the application log and stored on the alert preview.

### 4. Alert De-duplication Cache
To prevent notification storms, identical alerts for the same rule and endpoint are rate-limited with a 15-second cooldown window.
