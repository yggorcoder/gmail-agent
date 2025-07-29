from sqlalchemy import create_engine, Column, Integer, String, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class GmailAgent(Base):
    __tablename__ = 'gmail_agents'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email_gmail = Column(String)
    client_id = Column(LargeBinary)
    client_secret = Column(LargeBinary)
    refresh_token = Column(LargeBinary)