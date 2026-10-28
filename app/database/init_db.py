from sqlalchemy import text
from app.database.session import engine, Base, SessionLocal
from app.database.models import User, Product

SAMPLE_USERS = [
    {"name": "Sarah Connor", "email": "sarah.connor@cyberdyne.org", "role": "admin", "status": "active"},
    {"name": "Marcus Vance", "email": "marcus.v@acmecorp.io", "role": "developer", "status": "active"},
    {"name": "Amina El-Sayed", "email": "amina.elsayed@cloudscale.net", "role": "devops", "status": "active"},
    {"name": "Kenji Sato", "email": "k.sato@tokyotech.jp", "role": "analyst", "status": "active"},
    {"name": "Elena Rostova", "email": "elena.r@fintechlab.eu", "role": "member", "status": "suspended"}
]

SAMPLE_PRODUCTS = [
    {"sku": "SRV-ENT-01", "name": "Enterprise API Gateway Pro", "category": "Cloud Services", "price": 499.00, "stock": 42},
    {"sku": "DB-HA-CLUSTER", "name": "High-Availability DB Cluster", "category": "Database", "price": 1250.00, "stock": 15},
    {"sku": "MON-DASH-SUB", "name": "Real-time Telemetry Dashboard Suite", "category": "Observability", "price": 199.00, "stock": 100},
    {"sku": "SEC-WAF-RULE", "name": "Intelligent WAF & Rate Limiter Module", "category": "Security", "price": 299.00, "stock": 58},
    {"sku": "LOG-PIPE-TB", "name": "High-Throughput Log Ingestion Pipeline", "category": "Infrastructure", "price": 650.00, "stock": 25}
]

def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_telemetry_indexes()

    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            for u in SAMPLE_USERS:
                db.add(User(**u))
            db.commit()

        if db.query(Product).count() == 0:
            for p in SAMPLE_PRODUCTS:
                db.add(Product(**p))
            db.commit()
    finally:
        db.close()


def _ensure_telemetry_indexes():
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_requests_status ON api_request_logs(status_code)",
        "CREATE INDEX IF NOT EXISTS idx_requests_time ON api_request_logs(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_requests_path ON api_request_logs(path)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alert_logs(rule_name)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_status ON alert_logs(status)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
