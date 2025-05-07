from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from sqlalchemy import UniqueConstraint

class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("source", "timestamp", name="_source_ts_uc"),)

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String)
    timestamp = Column(String)

    # AbuseIPDB-specific
    abuse_type = Column(String)
    abuse_ip = Column(String, index=True)
    abuse_geo = Column(JSON, nullable=True)
    abuse_confidence_score = Column(Integer, nullable=True)
    abuse_total_reports = Column(Integer, nullable=True)
    abuse_distinct_users = Column(Integer, nullable=True)
    abuse_reports = Column(JSON, nullable=True)

    # OTX-specific
    otx_name = Column(String, nullable=True)
    otx_description = Column(String, nullable=True)