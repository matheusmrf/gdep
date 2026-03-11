from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint

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


class CPIEnvironment(Base):
    __tablename__ = "cpi_environments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    environment_type = Column(String, nullable=False, default="prod")  # prod, qa, sandbox
    cpi_host = Column(String, nullable=True)
    cpi_username = Column(String, nullable=True)
    cpi_password_encrypted = Column(String, nullable=True)
    cpi_tenant_id = Column(String, nullable=True)
    is_active = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "integration_id", name="uq_favorite_user_integration"),
    )


class AlertSettings(Base):
    __tablename__ = "alert_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    enabled = Column(Integer, nullable=False, default=0)
    email_to = Column(String, nullable=True)
    error_rate_threshold = Column(Float, nullable=False, default=0.05)
    processing_time_threshold = Column(Float, nullable=False, default=1000.0)
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_user = Column(String, nullable=True)
    smtp_password_encrypted = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SyncSchedule(Base):
    __tablename__ = "sync_schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    enabled = Column(Integer, nullable=False, default=0)
    hour = Column(Integer, nullable=False, default=6)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
