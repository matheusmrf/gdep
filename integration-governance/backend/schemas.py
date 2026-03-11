from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None


class ORMBaseModel(BaseModel):
    if ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)
    else:
        class Config:
            orm_mode = True


class UserRead(ORMBaseModel):
    id: int
    name: str
    email: str
    created_at: datetime


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class CPISettingsRequest(BaseModel):
    cpi_host: str = Field(min_length=3, max_length=255)
    cpi_username: str = Field(min_length=2, max_length=255)
    cpi_password: str = Field(min_length=4, max_length=255)
    cpi_tenant_id: str = Field(min_length=2, max_length=120)


class CPISettingsResponse(BaseModel):
    cpi_host: Optional[str] = None
    cpi_username: Optional[str] = None
    cpi_tenant_id: Optional[str] = None
    has_password: bool
    updated_at: Optional[datetime] = None


class POSettingsRequest(BaseModel):
    po_host: str = Field(min_length=3, max_length=255)
    po_username: str = Field(min_length=2, max_length=255)
    po_password: str = Field(min_length=4, max_length=255)


class POSettingsResponse(BaseModel):
    po_host: Optional[str] = None
    po_username: Optional[str] = None
    has_password: bool
    updated_at: Optional[datetime] = None


class SyncCPIRequest(BaseModel):
    reset: bool = False
    include_mpl: bool = True
    message_limit: int = Field(default=100, ge=1, le=100)


class SyncPORequest(BaseModel):
    reset: bool = False
    days: int = Field(default=1, ge=1, le=30)
    message_limit: int = Field(default=5000, ge=100, le=20000)


class IntegrationBase(BaseModel):
    name: str
    platform: str
    source_system: str
    target_system: str
    department: str = "Operações"
    monthly_volume: int
    error_count: int
    error_rate: float
    avg_processing_time: float
    business_weight: int = Field(ge=1, le=10)
    score: float
    criticality: str


class IntegrationRead(IntegrationBase, ORMBaseModel):
    id: int
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    external_id: Optional[str] = None
    external_source: Optional[str] = None
    cpi_symbolic_name: Optional[str] = None
    cpi_artifact_type: Optional[str] = None
    cpi_version: Optional[str] = None
    cpi_state: Optional[str] = None
    cpi_deployed: int = 0
    cpi_endpoint_count: int = 0
    cpi_endpoint_urls: Optional[str] = None
    cpi_sender: Optional[str] = None
    cpi_receiver: Optional[str] = None
    cpi_integration_flow_name: Optional[str] = None
    cpi_artifact_name: Optional[str] = None
    last_synced: Optional[datetime] = None


class PaginatedIntegrationsResponse(BaseModel):
    items: List[IntegrationRead]
    total: int
    skip: int
    limit: int


class SummaryResponse(BaseModel):
    total_integrations: int
    average_score: float
    total_monthly_volume: int
    total_error_count: int
    criticality_distribution: Dict[str, int]


class AlertItem(BaseModel):
    integration_id: int
    integration_name: str
    severity: str
    message: str


class AlertResponse(BaseModel):
    generated_at: datetime
    alerts: List[AlertItem]


# --- CPIEnvironment ---

class CPIEnvironmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    environment_type: str = Field(default="prod")  # prod, qa, sandbox
    cpi_host: str = Field(min_length=3, max_length=255)
    cpi_username: str = Field(min_length=2, max_length=255)
    cpi_password: str = Field(min_length=4, max_length=255)
    cpi_tenant_id: str = Field(min_length=2, max_length=120)


class CPIEnvironmentRead(ORMBaseModel):
    id: int
    name: str
    environment_type: str
    cpi_host: Optional[str] = None
    cpi_username: Optional[str] = None
    cpi_tenant_id: Optional[str] = None
    is_active: int
    created_at: datetime


# --- Favorite ---

class FavoriteRead(ORMBaseModel):
    id: int
    integration_id: int
    created_at: datetime


# --- AlertSettings ---

class AlertSettingsRequest(BaseModel):
    enabled: bool = False
    email_to: Optional[str] = None
    error_rate_threshold: float = Field(default=0.05, ge=0, le=1)
    processing_time_threshold: float = Field(default=1000.0, ge=0)
    smtp_host: Optional[str] = None
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None


class AlertSettingsRead(ORMBaseModel):
    id: int
    enabled: int
    email_to: Optional[str] = None
    error_rate_threshold: float
    processing_time_threshold: float
    smtp_host: Optional[str] = None
    smtp_port: int
    smtp_user: Optional[str] = None
    has_smtp_password: bool = False


# --- SyncSchedule ---

class SyncScheduleRequest(BaseModel):
    enabled: bool = False
    hour: int = Field(default=6, ge=0, le=23)


class SyncScheduleRead(ORMBaseModel):
    id: int
    enabled: int
    hour: int
    last_run: Optional[datetime] = None
