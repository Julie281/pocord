from sqlalchemy import Column, String, JSON, DateTime
from app.db.session import Base
from datetime import datetime
import uuid

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)

    transcript = Column(String)
    summary = Column(String)
    topics = Column(JSON)
    tasks = Column(JSON)
    speakers = Column(JSON)
    metrics = Column(JSON)
    audio_path = Column(String)