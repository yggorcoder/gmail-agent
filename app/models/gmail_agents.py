from sqlalchemy import Column, Integer, String, LargeBinary
from app.apis.database_connection import Base  

class GmailAgent(Base):
    __tablename__ = 'gmail_agents'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email_gmail = Column(String)
    client_id = Column(LargeBinary)
    client_secret = Column(LargeBinary)
    refresh_token = Column(LargeBinary)