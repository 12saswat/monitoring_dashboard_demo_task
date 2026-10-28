from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.init_db import init_db
from app.middleware.monitoring import APIMonitoringMiddleware
from app.routers import api, monitoring_api, dashboard

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

init_db()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(APIMonitoringMiddleware)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(dashboard.router)
app.include_router(api.router)
app.include_router(monitoring_api.router)

@app.get("/metrics", include_in_schema=False)
def root_metrics():
    return monitoring_api.prometheus_metrics()
