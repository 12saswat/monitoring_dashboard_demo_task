# Operational Runbook: Troubleshooting & Maintenance

This runbook guides DevOps, SRE, and development engineers through maintaining, troubleshooting, and tuning the FastAPI API Sentinel monitoring platform.

---

## 1. Quick Verification & Smoke Testing

Run the automated test suite to verify all endpoints and monitoring components:

```bash
# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
.\.venv\Scripts\activate   # On Windows

# Run full pytest suite
python -m pytest -v

# Run the failure scenarios validation script
python scripts/test_all_scenarios.py
```

---

## 2. Troubleshooting Guide

### Issue: High 500 Error Count on the Dashboard
1. Open the dashboard at `http://localhost:8000/dashboard`.
2. Locate the failed request in the **Live Request Telemetry** table.
3. Click **🔍 View RCA** to open the root cause modal.
4. Review the captured stack trace to identify the exact file and line number.
5. If the issue is related to SQLite database locks:
   - Check if `monitoring.db-wal` or `monitoring.db-shm` files exist.
   - Verify `PRAGMA busy_timeout=5000` is active in `app/database/session.py`.

### Issue: Latency Spike (>3.0s SLA Alert)
1. Verify host system CPU and RAM usage in the dashboard status banner.
2. Ensure endpoints are async: `async def` for I/O-bound operations and standard `def` with background thread pools for CPU-bound tasks.
3. Check if SQLite queries need indexing:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_requests_status ON api_request_logs(status_code);
   CREATE INDEX IF NOT EXISTS idx_requests_time ON api_request_logs(timestamp);
   ```

### Issue: Missing Prometheus Metrics Scrape
1. Test the `/metrics` endpoint manually:
   ```bash
   curl -i http://localhost:8000/metrics
   ```
2. Verify that Prometheus counters such as `fastapi_requests_total` are present.
3. Start Prometheus and Grafana (FastAPI must already be running, default port 8000):
   ```bash
   docker compose up -d
   ```
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (admin/admin). Dashboard **FastAPI API Sentinel** is auto-provisioned.
   - Scrape config lives in `monitoring/prometheus.yml` and uses `host.docker.internal:8000`.
   If the API uses another port (see `PORT` in `.env`), update that target.

---

## 3. Maintenance Procedures

### SQLite Database Maintenance & Log Pruning
Telemetry logs accumulate over time. Use this maintenance procedure to keep database file sizes manageable:

```bash
# Open SQLite CLI
sqlite3 monitoring.db

-- 1. Remove telemetry logs older than 7 days
DELETE FROM api_request_logs WHERE timestamp < datetime('now', '-7 days');

-- 2. Clear resolved alerts older than 30 days
DELETE FROM alert_logs WHERE status = 'RESOLVED' AND created_at < datetime('now', '-30 days');

-- 3. Reclaim unused disk space and defragment
VACUUM;

-- 4. Check database integrity
PRAGMA integrity_check;
```

### Rotating Authentication Tokens
Update `AUTH_DEMO_TOKEN` in `.env`:
```bash
AUTH_DEMO_TOKEN="new-secure-token-2026"
```
Restart the service to apply changes.

### Enabling Live Slack Webhook
1. Go to your Slack Workspace $\rightarrow$ App Directory $\rightarrow$ Incoming Webhooks.
2. Copy the Webhook URL.
3. Update `.env`:
   ```bash
   SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00/B00/XXXX"
   ```
4. Restart the FastAPI service. Alerts will now stream live into your designated Slack channel.

### Enabling a live call / pager webhook
Set `CALL_WEBHOOK_URL` in `.env` to any HTTPS endpoint that accepts JSON (Twilio Function, n8n, PagerDuty custom webhook). CRITICAL alerts POST `{alert_id, severity, title, message}`. Leave it empty to keep the simulated pager log.

---

## 4. Grafana + Prometheus maintenance
- Keep the FastAPI process listening on the port Prometheus scrapes.
- Grafana dashboard JSON: `monitoring/grafana/dashboards/fastapi-sentinel.json`.
- After changing scrape targets, restart Prometheus: `docker compose restart prometheus`.
