from pydantic import BaseModel, EmailStr
from typing import Optional

class AgentIn(BaseModel):
    name: str
    email_gmail: EmailStr
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None

    class Config:
        from_attributes = True # ou orm_mode = True para Pydantic < 2.0