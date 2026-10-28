import time
import uuid
import traceback
from typing import Callable
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.background import BackgroundTasks

from app.core.config import settings
from app.database.session import SessionLocal
from app.database.models import RequestLog
from app.services.rca_engine import RootCauseAnalysisEngine
from app.services.alert_service import AlertService
from app.services.metrics_service import MetricsService

EXCLUDED_PATHS = {"/metrics", "/favicon.ico", "/static"}


class APIMonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if any(request.url.path.startswith(p) for p in EXCLUDED_PATHS):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        client_ip = request.client.host if request.client else "127.0.0.1"
        user_agent = request.headers.get("user-agent", "")
        start_time = time.perf_counter()

        status_code = 500
        error_type = None
        error_message = None
        error_tb = None
        response = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)
            error_tb = traceback.format_exc()
            status_code = 500
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred processing your request.",
                    "request_id": request_id,
                    "rca_available": True
                }
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        is_error = status_code >= 400

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)

        MetricsService.record_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            is_error=is_error
        )

        tasks = BackgroundTasks()
        if response.background is not None:
            tasks.add_task(response.background)
        tasks.add_task(
            self._save_log_to_db,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
            user_agent=user_agent,
            is_error=is_error,
            error_type=error_type,
            error_message=error_message,
            error_tb=error_tb
        )
        tasks.add_task(
            self._evaluate_alerts,
            status_code=status_code,
            path=request.url.path,
            method=request.method,
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            error_tb=error_tb,
            client_ip=client_ip
        )
        tasks.add_task(MetricsService.evaluate_aggregate_alerts)
        response.background = tasks
        return response

    def _save_log_to_db(self, **kwargs):
        db = SessionLocal()
        try:
            log_entry = RequestLog(
                request_id=kwargs["request_id"],
                timestamp=datetime.now(timezone.utc),
                method=kwargs["method"],
                path=kwargs["path"],
                status_code=kwargs["status_code"],
                duration_ms=kwargs["duration_ms"],
                client_ip=kwargs["client_ip"],
                user_agent=kwargs["user_agent"],
                is_error=kwargs["is_error"],
                error_type=kwargs["error_type"],
                error_message=kwargs["error_message"],
                error_traceback=kwargs["error_tb"]
            )
            db.add(log_entry)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _evaluate_alerts(
        self,
        status_code: int,
        path: str,
        method: str,
        duration_ms: float,
        error_type: str,
        error_message: str,
        error_tb: str,
        client_ip: str
    ):
        rca_kwargs = dict(
            status_code=status_code,
            path=path,
            method=method,
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            error_traceback=error_tb,
            client_ip=client_ip
        )

        is_health_path = path.rstrip("/").endswith("health") or "health-failure" in path or "downtime" in path
        is_outage = status_code == 503 or error_type in {"ServiceHealthError", "ApiDowntime"}

        if is_outage:
            if "downtime" in path or error_type == "ApiDowntime":
                rca = RootCauseAnalysisEngine.downtime_rca(path, method, error_message)
                AlertService.trigger_alert(
                    rule_name="API_DOWNTIME",
                    severity="CRITICAL",
                    title=f"API Downtime on {method} {path}",
                    description=error_message or f"HTTP {status_code} service unavailable",
                    rca=rca
                )
            rca = RootCauseAnalysisEngine.health_failure_rca(path, method, error_message)
            AlertService.trigger_alert(
                rule_name="SERVICE_HEALTH_FAILURE",
                severity="CRITICAL",
                title=f"Service Health Failure on {method} {path}",
                description=error_message or f"Health check returned HTTP {status_code}",
                rca=rca
            )
            if is_health_path and "downtime" not in path:
                downtime = RootCauseAnalysisEngine.downtime_rca(path, method, error_message)
                AlertService.trigger_alert(
                    rule_name="API_DOWNTIME",
                    severity="CRITICAL",
                    title=f"API Downtime on {method} {path}",
                    description=error_message or "Health probe failed; API treated as down",
                    rca=downtime
                )
            return

        if status_code >= 500:
            rca = RootCauseAnalysisEngine.analyze(**rca_kwargs)
            AlertService.trigger_alert(
                rule_name="HTTP_500_INTERNAL_SERVER_ERROR",
                severity="CRITICAL",
                title=f"Critical 500 Error on {method} {path}",
                description=f"Server returned status {status_code} with exception {error_type or 'ServerError'}: {error_message or 'Unknown'}",
                rca=rca
            )
            return

        if duration_ms >= (settings.latency_threshold_sec * 1000.0):
            rca = RootCauseAnalysisEngine.analyze(**rca_kwargs)
            AlertService.trigger_alert(
                rule_name="LATENCY_SLA_BREACH",
                severity="WARNING",
                title=f"Response Time SLA Breached on {path}",
                description=f"Response time of {duration_ms:.1f}ms exceeded the {settings.latency_threshold_sec * 1000}ms SLA threshold.",
                rca=rca
            )
            return

        if status_code == 401:
            rca = RootCauseAnalysisEngine.analyze(**{**rca_kwargs, "error_type": "AuthenticationError"})
            AlertService.trigger_alert(
                rule_name="AUTH_FAILURE_DETECTED",
                severity="WARNING",
                title=f"Authentication Failure on {path}",
                description=f"Unauthorized request detected from IP {client_ip}.",
                rca=rca
            )
            return

        if status_code == 429:
            rca = RootCauseAnalysisEngine.analyze(**rca_kwargs)
            AlertService.trigger_alert(
                rule_name="RATE_LIMIT_EXCEEDED",
                severity="WARNING",
                title=f"Rate Limit Exceeded on {path}",
                description=f"Client {client_ip} exceeded throttling quota.",
                rca=rca
            )
