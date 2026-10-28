import asyncio
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.database.models import User, Product
from app.middleware.rate_limiter import rate_limiter
from app.services.metrics_service import MetricsService

router = APIRouter()

@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    sys_metrics = MetricsService.refresh_system_metrics()
    
    try:
        user_count = db.query(User).count()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        raise HTTPException(status_code=503, detail=f"Database unreachable: {str(e)}")

    return {
        "status": "UP",
        "service": settings.app_name,
        "environment": settings.app_env,
        "database": {
            "status": db_status,
            "engine": "SQLite (WAL mode)",
            "records_indexed": user_count,
            "ping_ms": sys_metrics["db_ping_ms"]
        },
        "system": {
            "cpu_percent": sys_metrics["cpu_percent"],
            "memory_percent": sys_metrics["memory_percent"],
            "uptime_seconds": sys_metrics["uptime_seconds"]
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {
        "count": len(users),
        "data": [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "status": u.status
            }
            for u in users
        ]
    }

@router.get("/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return {
        "count": len(products),
        "data": [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "category": p.category,
                "price": p.price,
                "stock": p.stock
            }
            for p in products
        ]
    }

@router.get("/secure-data")
def get_secure_data(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization header. Expected 'Bearer <token>'."
        )
    
    token = authorization.split(" ")[1]
    if token != settings.auth_demo_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token. Verification failed."
        )

    return {
        "status": "authenticated",
        "secret_vault_code": "ALPHA-DELTA-9871",
        "access_level": "RESTRICTED",
        "authorized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@router.get("/simulate-timeout")
async def simulate_timeout(delay_seconds: float = Query(3.5)):
    await asyncio.sleep(delay_seconds)
    return {
        "status": "completed_with_latency",
        "simulated_delay_sec": delay_seconds,
        "message": f"Response completed after {delay_seconds}s (Threshold is {settings.latency_threshold_sec}s)"
    }

@router.get("/simulate-error")
def simulate_error(error_kind: str = Query("math")):
    if error_kind == "math":
        # pyrefly: ignore[division-by-zero]
        x = 42 / 0
        return {"result": x}
    elif error_kind == "key":
        payload = {}
        return {"value": payload["missing_transaction_id"]}
    else:
        raise RuntimeError("Simulated critical backend microservice outage")

@router.get("/simulate-rate-limit")
def simulate_rate_limit(
    request: Request,
    force_breach: bool = Query(True)
):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if force_breach:
        rate_limiter.force_exceed(client_ip)
    rate_limiter.check_rate_limit(client_ip)
    return {"status": "ok", "quota_remaining": rate_limiter.remaining(client_ip)}

@router.get("/simulate-health-failure")
def simulate_health_failure():
    raise HTTPException(
        status_code=503,
        detail="Service health failure: dependency probe reported unhealthy.",
        headers={"Retry-After": "30"}
    )

@router.get("/simulate-downtime")
def simulate_downtime():
    raise HTTPException(
        status_code=503,
        detail="API downtime: sample service is unavailable.",
        headers={"Retry-After": "30"}
    )
