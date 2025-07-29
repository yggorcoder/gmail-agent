from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from app.database import SessionLocal, GmailAgent
from app.encryption import get_cipher_suite
from app.gmail_service import fetch_recent_emails
from sqlalchemy.orm import Session

router = APIRouter()

class EmailOut(BaseModel):
    sender: str
    subject: str
    content: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/emails/recent", response_model=list[EmailOut])
def get_recent_emails(limit: int = Query(5, ge=1, le=50), agent_id: int = None, db: Session = Depends(get_db)):
    if agent_id:
        agent = db.query(GmailAgent).filter(GmailAgent.id == agent_id).first()
    else:
        agent = db.query(GmailAgent).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    try:
        cipher = get_cipher_suite()
        client_id = cipher.decrypt(agent.client_id).decode()
        client_secret = cipher.decrypt(agent.client_secret).decode()
        refresh_token = cipher.decrypt(agent.refresh_token).decode()
        emails = fetch_recent_emails(client_id, client_secret, refresh_token, max_results=limit)
        result = [
            EmailOut(sender=email['from'], subject=email['subject'], content=email['body'])
            for email in emails
        ]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving emails: {str(e)}") 