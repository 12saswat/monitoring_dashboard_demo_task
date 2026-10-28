from typing import Any, Dict, Optional


class RootCauseAnalysisEngine:
    """
    Automated diagnostic engine that examines HTTP failure contexts,
    stack traces, latency timings, and client headers to determine
    the root cause and suggest actionable remediation steps.
    """

    @classmethod
    def analyze(
        cls,
        status_code: int,
        path: str,
        method: str,
        duration_ms: float,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
        client_ip: Optional[str] = "127.0.0.1"
    ) -> Dict[str, Any]:
        """Performs structured diagnosis based on failure signature."""

        if status_code == 401 or error_type == "AuthenticationError":
            return cls.auth_failure_rca(path, method, client_ip)

        if status_code == 429 or "rate-limit" in path.lower():
            return cls.rate_limit_rca(path, client_ip)

        if duration_ms >= 3000.0 or "timeout" in path.lower():
            return cls.latency_rca(path, method, duration_ms)

        if status_code == 503 or error_type in {"ServiceHealthError", "ApiDowntime"}:
            if error_type == "ApiDowntime" or "downtime" in path.lower():
                return cls.downtime_rca(path, method, error_message)
            return cls.health_failure_rca(path, method, error_message)

        if status_code >= 500 or error_traceback:
            return cls.server_error_rca(
                status_code, path, method, error_type, error_message, error_traceback
            )

        return {
            "rule_name": f"HTTP_{status_code}_CLIENT_ERROR",
            "severity": "INFO",
            "title": f"Client Request Failure ({status_code}) on {method} {path}",
            "summary": f"Request failed with HTTP {status_code}: {error_message or 'Resource not found or bad payload.'}",
            "technical_details": {
                "http_status": status_code,
                "target_endpoint": path,
                "client_ip": client_ip
            },
            "recommendation": "Review client request parameters and ensure endpoints conform to OpenAPI spec."
        }

    @classmethod
    def auth_failure_rca(cls, path: str, method: str, client_ip: Optional[str]) -> Dict[str, Any]:
        return {
            "rule_name": "AUTH_FAILURE_DETECTED",
            "severity": "WARNING",
            "title": f"Unauthorized Access Attempt on {method} {path}",
            "summary": (
                f"Client request from {client_ip} lacked valid authentication credentials. "
                f"The Authorization header was either missing or contained an invalid/expired Bearer token."
            ),
            "technical_details": {
                "http_status": 401,
                "target_endpoint": path,
                "failure_mechanism": "Missing or rejected Authorization: Bearer token header",
                "client_ip": client_ip,
            },
            "recommendation": (
                "1. Verify that the client is sending 'Authorization: Bearer sentinel-secure-token-2026'.\n"
                "2. Check if the token has expired or if AUTH_DEMO_TOKEN was rotated in .env.\n"
                "3. Inspect auth logs for brute-force or credential stuffing patterns from this IP."
            )
        }

    @classmethod
    def latency_rca(cls, path: str, method: str, duration_ms: float) -> Dict[str, Any]:
        return {
            "rule_name": "LATENCY_SLA_BREACH",
            "severity": "WARNING",
            "title": f"High Response Time ({duration_ms:.1f}ms) Exceeded 3000ms SLA",
            "summary": (
                f"Request to {method} {path} took {duration_ms:.2f}ms to complete, "
                f"which breaches the defined service level agreement of 3.0 seconds."
            ),
            "technical_details": {
                "duration_ms": duration_ms,
                "sla_threshold_ms": 3000.0,
                "target_endpoint": path,
                "suspected_cause": "Blocking I/O operation, heavy compute loop, or external upstream timeout."
            },
            "recommendation": (
                "1. Check for synchronous time.sleep or un-awaited I/O calls blocking the async event loop.\n"
                "2. Add database query indexes if latency originates from slow SQLite reads/writes.\n"
                "3. Offload compute-heavy processing to async task queues (Celery/RQ)."
            )
        }

    @classmethod
    def server_error_rca(
        cls,
        status_code: int,
        path: str,
        method: str,
        error_type: Optional[str],
        error_message: Optional[str],
        error_traceback: Optional[str]
    ) -> Dict[str, Any]:
        summary = (
            f"Unhandled server exception during {method} {path}. "
            f"Exception [{error_type or 'ServerError'}]: {error_message or 'Internal Server Error'}"
        )
        fix_steps = [
            "1. Inspect the traceback stack frame where the exception was raised.",
            "2. Validate all incoming request payload types with Pydantic schemas before processing.",
            "3. Wrap risky operations in try/except blocks with graceful fallbacks."
        ]
        if error_type == "ZeroDivisionError" or "division by zero" in str(error_message).lower():
            summary += " -> Triggered by unhandled arithmetic division by zero."
            fix_steps.insert(0, "CRITICAL: Guard denominators with `if denominator != 0:` check.")
        elif "operationalerror" in str(error_type).lower() or "database" in str(error_message).lower():
            summary += " -> Triggered by SQLite lock contention or missing column."
            fix_steps.insert(0, "CRITICAL: Check SQLite WAL mode and busy timeout settings.")

        preview = None
        if error_traceback:
            preview = (error_traceback[:350] + "...") if len(error_traceback) > 350 else error_traceback

        return {
            "rule_name": "HTTP_500_INTERNAL_SERVER_ERROR",
            "severity": "CRITICAL",
            "title": f"Unhandled Server Exception on {method} {path}",
            "summary": summary,
            "technical_details": {
                "http_status": status_code,
                "error_type": error_type or "InternalServerError",
                "error_message": error_message or "Internal Server Error",
                "stacktrace_preview": preview
            },
            "recommendation": "\n".join(fix_steps)
        }

    @classmethod
    def rate_limit_rca(cls, path: str, client_ip: Optional[str]) -> Dict[str, Any]:
        return {
            "rule_name": "RATE_LIMIT_EXCEEDED",
            "severity": "WARNING",
            "title": f"Rate Limit Throttling Triggered on {path}",
            "summary": (
                f"Client {client_ip} exceeded the allowed request quota on {path}. "
                f"Requests were actively throttled with HTTP 429 (10 requests per 10-second sliding window)."
            ),
            "technical_details": {
                "http_status": 429,
                "client_ip": client_ip,
                "rate_policy": "Sliding window limit exceeded (max 10 requests per 10-second window)",
                "protection_mechanism": "Token Bucket / Sliding Window in-memory limiter"
            },
            "recommendation": (
                "1. Instruct client to observe 'Retry-After' response header.\n"
                "2. Apply exponential backoff with jitter in API client SDKs.\n"
                "3. For authenticated enterprise partners, increase rate tier in API Gateway."
            )
        }

    @classmethod
    def failure_rate_rca(cls, error_pct: float, window_size: int, threshold: float) -> Dict[str, Any]:
        return {
            "rule_name": "INCREASED_FAILURE_RATE",
            "severity": "WARNING",
            "title": f"Failure Rate {error_pct:.1f}% Exceeded {threshold}% Threshold",
            "summary": (
                f"Error percentage in the last {window_size} requests reached {error_pct:.1f}%, "
                f"above the configured {threshold}% failure-rate alert."
            ),
            "technical_details": {
                "error_rate_percent": error_pct,
                "window_size": window_size,
                "threshold_percent": threshold
            },
            "recommendation": (
                "1. Review recent 4xx/5xx entries in Live Request Telemetry.\n"
                "2. Correlate with deploy time, auth failures, or upstream timeouts.\n"
                "3. Halt traffic bursts or roll back the last change if errors persist."
            )
        }

    @classmethod
    def downtime_rca(cls, path: str, method: str, error_message: Optional[str]) -> Dict[str, Any]:
        return {
            "rule_name": "API_DOWNTIME",
            "severity": "CRITICAL",
            "title": f"API Downtime Detected on {method} {path}",
            "summary": (
                "The API reported an outage (HTTP 503). Clients cannot complete health or data requests. "
                f"Detail: {error_message or 'service unavailable'}"
            ),
            "technical_details": {
                "http_status": 503,
                "target_endpoint": path,
                "failure_mechanism": "Service unavailable / dependency outage"
            },
            "recommendation": (
                "1. Confirm the uvicorn process is running (`python run.py`).\n"
                "2. Verify SQLite file locks and disk space for monitoring.db.\n"
                "3. Restore /health to HTTP 200 before sending client traffic."
            )
        }

    @classmethod
    def health_failure_rca(cls, path: str, method: str, error_message: Optional[str]) -> Dict[str, Any]:
        return {
            "rule_name": "SERVICE_HEALTH_FAILURE",
            "severity": "CRITICAL",
            "title": f"Service Health Check Failed on {method} {path}",
            "summary": (
                "Server health probe failed. Database connectivity or host resources are outside safe limits. "
                f"Detail: {error_message or 'health check returned unhealthy'}"
            ),
            "technical_details": {
                "http_status": 503,
                "target_endpoint": path,
                "failure_mechanism": "Health endpoint or resource threshold breach"
            },
            "recommendation": (
                "1. Inspect CPU, RAM, and disk on the dashboard status banner.\n"
                "2. Check SQLite ping latency and WAL/SHM files.\n"
                "3. Restart the service after clearing the unhealthy dependency."
            )
        }
