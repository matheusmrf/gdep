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


class SyncCPIRequest(BaseModel):
    reset: bool = False
    include_mpl: bool = True
    message_limit: int = Field(default=20, ge=1, le=100)


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
