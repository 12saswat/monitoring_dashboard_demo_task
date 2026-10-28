from fastapi import APIRouter, Response, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from prometheus_client import CONTENT_TYPE_LATEST

from app.database.session import get_db
from app.database.models import RequestLog, AlertLog
from app.services.metrics_service import MetricsService
from app.services.rca_engine import RootCauseAnalysisEngine

router = APIRouter(prefix="/api/monitoring")

@router.get("/metrics")
def prometheus_metrics():
    metrics_data = MetricsService.get_prometheus_metrics()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

@router.get("/stats")
def get_dashboard_stats():
    return MetricsService.get_dashboard_summary()

@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    alerts = db.query(AlertLog).order_by(desc(AlertLog.id)).limit(50).all()
    return [
        {
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
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if a.created_at else ""
        }
        for a in alerts
    ]

@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(AlertLog).filter(AlertLog.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "RESOLVED"
    db.commit()
    return {"status": "resolved", "alert_id": alert_id}

@router.get("/rca/{request_id}")
def get_request_rca(request_id: str, db: Session = Depends(get_db)):
    log_entry = db.query(RequestLog).filter(RequestLog.request_id == request_id).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Telemetry log entry not found")
    
    rca = RootCauseAnalysisEngine.analyze(
        status_code=log_entry.status_code,
        path=log_entry.path,
        method=log_entry.method,
        duration_ms=log_entry.duration_ms,
        error_type=log_entry.error_type,
        error_message=log_entry.error_message,
        error_traceback=log_entry.error_traceback,
        client_ip=log_entry.client_ip
    )
    
    return {
        "request_id": log_entry.request_id,
        "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else None,
        "method": log_entry.method,
        "path": log_entry.path,
        "status_code": log_entry.status_code,
        "duration_ms": log_entry.duration_ms,
        "client_ip": log_entry.client_ip,
        "error_type": log_entry.error_type,
        "error_message": log_entry.error_message,
        "error_traceback": log_entry.error_traceback,
        "analysis": rca
    }
