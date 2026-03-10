from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    cpi_host = Column(String, nullable=True)
    cpi_username = Column(String, nullable=True)
    cpi_password_encrypted = Column(String, nullable=True)
    cpi_tenant_id = Column(String, nullable=True)
    settings_updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    platform = Column(String, nullable=False, default="CPI")
    cpi_host = Column(String, nullable=True)
    cpi_tenant_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    platform = Column(String, nullable=False, index=True)
    source_system = Column(String, nullable=False)
    target_system = Column(String, nullable=False)
    department = Column(String, nullable=False, default="Operações")
    monthly_volume = Column(Integer, nullable=False)
    error_count = Column(Integer, nullable=False)
    error_rate = Column(Float, nullable=False)
    avg_processing_time = Column(Float, nullable=False)
    business_weight = Column(Integer, nullable=False)
    score = Column(Float, nullable=False, index=True)
    criticality = Column(String, nullable=False, index=True)
    external_id = Column(String, nullable=True, index=True)
    external_source = Column(String, nullable=True, index=True)
    last_synced = Column(DateTime, default=datetime.utcnow, nullable=True)

    __table_args__ = (
        Index("idx_integrations_external_source_platform", "external_source", "platform"),
        Index("idx_integrations_tenant_score", "tenant_id", "score"),
        Index("idx_integrations_user_score", "user_id", "score"),
    )
