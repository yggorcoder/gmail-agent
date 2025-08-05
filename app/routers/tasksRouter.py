
from fastapi import APIRouter, Depends, HTTPException
from app.tasks.tasks import process_emails_task
from app.apis.database_connection import SessionLocal
from app.models.gmail_agents import GmailAgent
from sqlalchemy.orm import Session

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/tasks/process-emails/{agent_id}")
def trigger_process_emails(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(GmailAgent).filter(GmailAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    # This is where you would typically trigger a background task.
    # For simplicity, we'll call the function directly.
    # In a production environment, you would use a task queue like Celery.
    process_emails_task(agent_id)

    return {"message": f"Email processing task started for agent {agent_id}."}
