from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from app.summary_gen import generate_email_summary
import requests

router = APIRouter()

class EmailTextIn(BaseModel):
    email_body: str
    language: str = "pt"

class SummaryOut(BaseModel):
    summary: str

class SendSummaryIn(BaseModel):
    summary: str
    recipient_url: str
    metadata: dict = {}

    @validator("recipient_url")
    def validate_recipient_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Invalid recipient URL. Must be HTTP or HTTPS.")
        return v

class SendSummaryOut(BaseModel):
    status: str
    response_code: int
    response_body: str

class SendReplyIn(BaseModel):
    reply: str
    recipient_email: str
    recipient_url: str
    metadata: dict = {}

    @validator("recipient_url")
    def validate_recipient_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Invalid recipient URL. Must be HTTP or HTTPS.")
        return v

class SendReplyOut(BaseModel):
    status: str
    response_code: int
    response_body: str

@router.post("/summary", response_model=SummaryOut)
def summarize_email(data: EmailTextIn):
    try:
        summary = generate_email_summary(data.email_body, language=data.language)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

@router.post("/send-summary", response_model=SendSummaryOut)
def send_summary(data: SendSummaryIn):
    try:
        payload = {
            "summary": data.summary,
            "metadata": data.metadata
        }
        response = requests.post(data.recipient_url, json=payload, timeout=10)
        return {
            "status": "success" if response.ok else "failed",
            "response_code": response.status_code,
            "response_body": response.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending summary: {str(e)}")

@router.post("/send-reply", response_model=SendReplyOut)
def send_reply(data: SendReplyIn):
    try:
        payload = {
            "reply": data.reply,
            "recipient_email": data.recipient_email,
            "metadata": data.metadata
        }
        response = requests.post(data.recipient_url, json=payload, timeout=10)
        return {
            "status": "success" if response.ok else "failed",
            "response_code": response.status_code,
            "response_body": response.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending reply: {str(e)}") 