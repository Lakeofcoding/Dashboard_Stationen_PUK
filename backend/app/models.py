from sqlalchemy import Column, String
from app.db import Base

class Ack(Base):
    __tablename__ = "ack"

    case_id = Column(String, primary_key=True)
    station_id = Column(String, primary_key=True)

    ack_scope = Column(String, primary_key=True)   # 'case' | 'rule'
    scope_id = Column(String, primary_key=True)    # '*' oder rule_id

    acked_at = Column(String, nullable=False)      # ISO-UTC
    acked_by = Column(String, nullable=False)      # user_id
    comment = Column(String, nullable=True)
