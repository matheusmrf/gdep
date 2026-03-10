from sqlalchemy import Column, Float, Integer, String

from backend.database import Base


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    source_system = Column(String, nullable=False)
    target_system = Column(String, nullable=False)
    monthly_volume = Column(Integer, nullable=False)
    error_count = Column(Integer, nullable=False)
    error_rate = Column(Float, nullable=False)
    avg_processing_time = Column(Float, nullable=False)
    business_weight = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    criticality = Column(String, nullable=False)
