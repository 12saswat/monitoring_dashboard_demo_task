import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "FastAPI API Sentinel")
    app_env: str = os.getenv("APP_ENV", "development")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT") or 8000)
    
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'monitoring.db'}")
    auth_demo_token: str = os.getenv("AUTH_DEMO_TOKEN", "sentinel-secure-token-2026")
    
    latency_threshold_sec: float = float(os.getenv("ALERT_LATENCY_THRESHOLD_SEC", "3.0"))
    error_rate_threshold_pct: float = float(os.getenv("ALERT_ERROR_RATE_PERCENT", "20.0"))
    sliding_window_size: int = int(os.getenv("ALERT_WINDOW_SIZE", "20"))
    health_cpu_threshold: float = float(os.getenv("ALERT_CPU_PERCENT", "90.0"))
    health_memory_threshold: float = float(os.getenv("ALERT_MEMORY_PERCENT", "90.0"))
    
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    email_smtp_host: str = os.getenv("EMAIL_SMTP_HOST", "")
    email_smtp_port: int = int(os.getenv("EMAIL_SMTP_PORT") or 587)
    email_sender: str = os.getenv("EMAIL_SENDER", "")
    email_recipient: str = os.getenv("EMAIL_RECIPIENT", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")
    call_webhook_url: str = os.getenv("CALL_WEBHOOK_URL", "")

settings = Settings()
