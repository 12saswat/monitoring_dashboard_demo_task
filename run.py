import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.app_name} on http://{settings.host}:{settings.port}")
    print(f"Dashboard: http://localhost:{settings.port}/dashboard")
    print(f"Docs:      http://localhost:{settings.port}/docs")
    print(f"Metrics:   http://localhost:{settings.port}/metrics")
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
