from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.database.session import Base

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    role = Column(String(50), default="member")
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=utc_now)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    category = Column(String(80), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)


class RequestLog(Base):
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(36), index=True, nullable=False)
    timestamp = Column(DateTime, default=utc_now, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), index=True, nullable=False)
    status_code = Column(Integer, index=True, nullable=False)
    duration_ms = Column(Float, nullable=False)
    client_ip = Column(String(45), default="127.0.0.1")
    user_agent = Column(String(255), nullable=True)
    
    is_error = Column(Boolean, default=False, index=True)
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(36), unique=True, index=True, nullable=False)
    rule_name = Column(String(100), index=True, nullable=False)
    severity = Column(String(20), default="WARNING")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    
    rca_summary = Column(Text, nullable=False)
    rca_recommendation = Column(Text, nullable=False)
    
    channels_notified = Column(String(100), default="Email, Slack")
    notification_preview = Column(Text, nullable=True)
    
    status = Column(String(20), default="ACTIVE")
    created_at = Column(DateTime, default=utc_now, index=True)


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)
    db_ping_ms = Column(Float, nullable=False)
    is_healthy = Column(Boolean, default=True)
    details = Column(Text, nullable=True)
