import time
import psutil
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy import func, desc

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.database.models import RequestLog, AlertLog, HealthSnapshot
from app.services.alert_service import AlertService
from app.services.rca_engine import RootCauseAnalysisEngine

REQUESTS_TOTAL = Counter(
    "fastapi_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION_HISTOGRAM = Histogram(
    "fastapi_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
)

ACTIVE_ALERTS_GAUGE = Gauge(
    "fastapi_active_alerts_total",
    "Number of active unacknowledged alerts"
)

SYSTEM_CPU_GAUGE = Gauge(
    "fastapi_system_cpu_percent",
    "Host system CPU utilization percentage"
)

SYSTEM_MEMORY_GAUGE = Gauge(
    "fastapi_system_memory_percent",
    "Host system RAM utilization percentage"
)

APP_UPTIME_GAUGE = Gauge(
    "fastapi_uptime_seconds",
    "Process running uptime in seconds"
)

SYSTEM_DISK_GAUGE = Gauge(
    "fastapi_system_disk_percent",
    "Host system disk utilization percentage"
)

ERROR_RATE_GAUGE = Gauge(
    "fastapi_error_rate_percent",
    "Rolling HTTP 4xx/5xx error percentage"
)

START_TIME = time.time()

class MetricsService:
    """
    Maintains telemetry aggregation, Prometheus counters, and
    supplies real-time dashboard analytics from SQLite.
    """

    # In-memory fast circular buffer for sliding-window SLA calculations
    _recent_requests = deque(maxlen=200)
    _last_health_snapshot_ts: float = 0.0
    HEALTH_SNAPSHOT_INTERVAL_SEC = 30.0

    @classmethod
    def record_request(
        cls,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        is_error: bool
    ):
        """Records telemetry into Prometheus metrics and fast rolling cache."""
        # Prometheus updates
        REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
        REQUEST_DURATION_HISTOGRAM.labels(method=method, endpoint=endpoint).observe(duration_ms / 1000.0)
        
        # Sliding window buffer
        cls._recent_requests.append({
            "timestamp": time.time(),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "is_error": is_error
        })

    @classmethod
    def get_prometheus_metrics(cls) -> bytes:
        """Returns Prometheus scrape format text."""
        # Update gauges prior to export
        cls.refresh_system_metrics()
        return generate_latest()

    @classmethod
    def refresh_system_metrics(cls) -> Dict[str, Any]:
        """Reads system CPU, memory, disk, and DB ping latency."""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(".").percent
        uptime = time.time() - START_TIME

        # Test SQLite ping latency
        db_ping_start = time.perf_counter()
        db_healthy = True
        try:
            with engine.connect() as conn:
                conn.execute(func.now())
        except Exception:
            db_healthy = False
        db_ping_ms = round((time.perf_counter() - db_ping_start) * 1000, 2)

        SYSTEM_CPU_GAUGE.set(cpu)
        SYSTEM_MEMORY_GAUGE.set(mem)
        SYSTEM_DISK_GAUGE.set(disk)
        APP_UPTIME_GAUGE.set(uptime)

        return {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "disk_percent": disk,
            "db_ping_ms": db_ping_ms,
            "db_healthy": db_healthy,
            "uptime_seconds": round(uptime, 1)
        }

    @classmethod
    def evaluate_aggregate_alerts(cls) -> None:
        """Fires increased-failure-rate and resource health alerts from the rolling window."""
        window_size = max(1, settings.sliding_window_size)
        window = list(cls._recent_requests)[-window_size:]
        if len(window) >= window_size:
            failed = sum(1 for r in window if r["is_error"])
            error_pct = round(failed / len(window) * 100, 2)
            ERROR_RATE_GAUGE.set(error_pct)
            if error_pct >= settings.error_rate_threshold_pct:
                rca = RootCauseAnalysisEngine.failure_rate_rca(
                    error_pct, window_size, settings.error_rate_threshold_pct
                )
                AlertService.trigger_alert(
                    rule_name="INCREASED_FAILURE_RATE",
                    severity="WARNING",
                    title=f"Increased failure rate {error_pct}% over last {window_size} requests",
                    description=(
                        f"{failed}/{window_size} requests failed "
                        f"(threshold {settings.error_rate_threshold_pct}%)."
                    ),
                    rca=rca
                )

        sys_metrics = cls.refresh_system_metrics()
        if not sys_metrics["db_healthy"]:
            rca = RootCauseAnalysisEngine.health_failure_rca(
                "/health", "GET", "SQLite ping failed"
            )
            AlertService.trigger_alert(
                rule_name="SERVICE_HEALTH_FAILURE",
                severity="CRITICAL",
                title="SQLite health probe failed",
                description="Database ping raised an error; API treated as unhealthy.",
                rca=rca
            )
            AlertService.trigger_alert(
                rule_name="API_DOWNTIME",
                severity="CRITICAL",
                title="API downtime: database unreachable",
                description="Requests cannot be served while SQLite is unhealthy.",
                rca=RootCauseAnalysisEngine.downtime_rca("/health", "GET", "database unreachable")
            )
        elif (
            sys_metrics["cpu_percent"] >= settings.health_cpu_threshold
            or sys_metrics["memory_percent"] >= settings.health_memory_threshold
        ):
            rca = RootCauseAnalysisEngine.health_failure_rca(
                "/health",
                "GET",
                f"CPU {sys_metrics['cpu_percent']}% / RAM {sys_metrics['memory_percent']}%"
            )
            AlertService.trigger_alert(
                rule_name="SERVICE_HEALTH_FAILURE",
                severity="CRITICAL",
                title="Host resource health threshold exceeded",
                description=(
                    f"CPU {sys_metrics['cpu_percent']}% (limit {settings.health_cpu_threshold}%) "
                    f"RAM {sys_metrics['memory_percent']}% (limit {settings.health_memory_threshold}%)."
                ),
                rca=rca
            )

        cls._maybe_write_health_snapshot(sys_metrics)

    @classmethod
    def _maybe_write_health_snapshot(cls, sys_metrics: Dict[str, Any]) -> None:
        now = time.time()
        if now - cls._last_health_snapshot_ts < cls.HEALTH_SNAPSHOT_INTERVAL_SEC:
            return
        cls._last_health_snapshot_ts = now
        db = SessionLocal()
        try:
            db.add(HealthSnapshot(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=sys_metrics["cpu_percent"],
                memory_percent=sys_metrics["memory_percent"],
                disk_percent=sys_metrics["disk_percent"],
                db_ping_ms=sys_metrics["db_ping_ms"],
                is_healthy=sys_metrics["db_healthy"],
                details=f"uptime={sys_metrics['uptime_seconds']}s"
            ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    @classmethod
    def get_dashboard_summary(cls) -> Dict[str, Any]:
        """
        Aggregates operational metrics for the monitoring dashboard:
        - Total requests, success count, failure count, error rate %
        - Latency stats: average, P95
        - Service status: OPERATIONAL / DEGRADED / OUTAGE
        - Recent logs & active alerts
        """
        sys_metrics = cls.refresh_system_metrics()
        
        db = SessionLocal()
        try:
            total_requests = db.query(RequestLog).count()
            failed_requests = db.query(RequestLog).filter(RequestLog.status_code >= 400).count()
            
            # Error rate
            error_rate = round((failed_requests / total_requests * 100), 2) if total_requests > 0 else 0.0
            ERROR_RATE_GAUGE.set(error_rate)
            
            # Avg latency across all recorded requests
            avg_duration = db.query(func.avg(RequestLog.duration_ms)).scalar() or 0.0
            
            # Calculate P95 latency from recent requests in memory or SQLite
            durations = [r["duration_ms"] for r in cls._recent_requests]
            if durations:
                durations.sort()
                p95_idx = int(len(durations) * 0.95)
                p95_latency = durations[min(p95_idx, len(durations) - 1)]
            else:
                p95_latency = avg_duration

            # Recent 5xx count in the last 5 minutes
            five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            recent_5xx = db.query(RequestLog).filter(
                RequestLog.status_code >= 500,
                RequestLog.timestamp >= five_mins_ago
            ).count()

            # Active alerts count
            active_alerts_count = db.query(AlertLog).filter(AlertLog.status == "ACTIVE").count()
            ACTIVE_ALERTS_GAUGE.set(active_alerts_count)

            # Determine overall service status
            if not sys_metrics["db_healthy"] or recent_5xx >= 5:
                service_status = "CRITICAL OUTAGE"
                status_color = "#ef4444"
            elif recent_5xx > 0 or error_rate > 20.0 or avg_duration > 1500.0:
                service_status = "DEGRADED PERFORMANCE"
                status_color = "#f59e0b"
            else:
                service_status = "ALL SYSTEMS OPERATIONAL"
                status_color = "#10b981"

            # Compute Uptime percentage
            # Synthetic availability: ratio of non-5xx requests
            server_errors = db.query(RequestLog).filter(RequestLog.status_code >= 500).count()
            uptime_pct = round(100.0 - (server_errors / total_requests * 100), 2) if total_requests > 0 else 100.0
            if uptime_pct < 0:
                uptime_pct = 0.0

            # Latest 25 request logs for table
            recent_logs = db.query(RequestLog).order_by(desc(RequestLog.id)).limit(25).all()
            logs_data = []
            for item in recent_logs:
                logs_data.append({
                    "id": item.id,
                    "request_id": item.request_id,
                    "timestamp": item.timestamp.strftime("%H:%M:%S") if item.timestamp else "",
                    "method": item.method,
                    "path": item.path,
                    "status_code": item.status_code,
                    "duration_ms": round(item.duration_ms, 2),
                    "client_ip": item.client_ip,
                    "is_error": item.is_error,
                    "error_type": item.error_type,
                    "error_message": item.error_message
                })

            # Latest 10 alerts
            recent_alerts = db.query(AlertLog).order_by(desc(AlertLog.id)).limit(10).all()
            alerts_data = []
            for a in recent_alerts:
                alerts_data.append({
                    "id": a.id,
                    "alert_id": a.alert_id,
                    "rule_name": a.rule_name,
                    "severity": a.severity,
                    "title": a.title,
                    "description": a.description,
                    "rca_summary": a.rca_summary,
                    "rca_recommendation": a.rca_recommendation,
                    "channels_notified": a.channels_notified,
                    "notification_preview": a.notification_preview,
                    "status": a.status,
                    "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else ""
                })

            # Status code distribution counts (2xx, 3xx, 4xx, 5xx)
            status_dist = {
                "2xx": db.query(RequestLog).filter(RequestLog.status_code.between(200, 299)).count(),
                "3xx": db.query(RequestLog).filter(RequestLog.status_code.between(300, 399)).count(),
                "4xx": db.query(RequestLog).filter(RequestLog.status_code.between(400, 499)).count(),
                "5xx": db.query(RequestLog).filter(RequestLog.status_code >= 500).count()
            }

            return {
                "service_status": service_status,
                "status_color": status_color,
                "uptime_pct": uptime_pct,
                "total_requests": total_requests,
                "failed_requests": failed_requests,
                "error_rate": error_rate,
                "avg_duration_ms": round(avg_duration, 1),
                "p95_duration_ms": round(p95_latency, 1),
                "active_alerts_count": active_alerts_count,
                "system": sys_metrics,
                "status_distribution": status_dist,
                "recent_logs": logs_data,
                "recent_alerts": alerts_data
            }
        finally:
            db.close()
