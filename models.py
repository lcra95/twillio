from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Message(Base):
    __tablename__ = "message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    to = Column(String(50), nullable=False)
    # "from" es palabra reservada, por ello se utiliza "from_" y se mapea a la columna "from"
    from_ = Column("from", String(50), nullable=False)
    direction = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    number_id = Column(Integer, ForeignKey("number.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    mid = Column(String(255), nullable=True)
    reply_to = Column(String(255), nullable=True)
    object= Column(Text, nullable=False)


class Number(Base):
    __tablename__ = "number"

    id = Column(Integer, primary_key=True, autoincrement=True)
    number_type = Column(String(50), nullable=False)
    number = Column(String(50), nullable=False)
    account_sid = Column(String(255), nullable=True)
    auth_token = Column(String(255), nullable=True)
    agente_id = Column(String(255), nullable=True)
    status = Column(String(50), default='active')
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    agent_status = Column(Integer, nullable=False, default=0)
