from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, index=True)
    type = Column(String)
    source = Column(String)
    timestamp = Column(DateTime)
    geo = Column(JSON, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    total_reports = Column(Integer, nullable=True)
    distinct_users = Column(Integer, nullable=True)
    raw_reports = Column(JSON, nullable=True)