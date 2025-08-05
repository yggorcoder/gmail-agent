
from fastapi import FastAPI, Depends, Request, Query, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.apis.database_connection import engine, Base, SessionLocal
from app.models.gmail_agents import GmailAgent
from app.routers.emailRouter import router as email_router
from app.routers.summaryRouter import router as summary_router
from app.routers.tasksRouter import router as tasks_router
from app.models.schemas import AgentIn
from app.services.encryption import get_cipher_suite
from google_auth_oauthlib.flow import Flow
from urllib.parse import urlencode
import google.oauth2.credentials
import googleapiclient.discovery
import os


# Importing the httpx module to make HTTP requests
import httpx 

from dotenv import load_dotenv
load_dotenv()

SECRET_KEY_ENCRYPTION = os.getenv("SECRET_KEY_ENCRYPTION")
print(f"Loaded Encryption Key: {SECRET_KEY_ENCRYPTION[:5]}...{SECRET_KEY_ENCRYPTION[-5:]}")

Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- Google OAuth 2.0 Settings (Get from Google Cloud Console) ---
# It is highly recommended to load these environment variables (dotenv)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# This is the URI you should configure in the Google Cloud Console for "Web App"
# MAKE SURE THIS URL MATCHES YOUR CURRENT NGROK URL!
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI") # Load from .env for flexibility

# Initial verification of credentials
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("GOOGLE_CLIENT_ID ou GOOGLE_CLIENT_SECRET not configured in environment variables.")
if not GOOGLE_REDIRECT_URI:
    raise ValueError("GOOGLE_REDIRECT_URI not configured in environment variables.")

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    print(f"Unexpected error: {exc}") # Add a print for debugging
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": f"An unexpected error occurred: {exc}"},
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoint to Initiate OAuth 2.0 Authorization ---
# This endpoint now receives the agent_id to associate the authorization with.
@app.get("/authorize/{agent_id}")
async def google_auth_init(agent_id: int, db: Session = Depends(get_db)):
    """
    Initiates the OAuth 2.0 authorization flow with Google for a specific agent.
    Redirects the user to the Google consent page.
    """
    # Optional: Check if agent_id exists in DB before starting authorization
    db_agent = db.query(GmailAgent).filter(GmailAgent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found."
        )

    # Scopes required to interact with Gmail and obtain user information
    scope = (
        "https://www.googleapis.com/auth/gmail.modify " # Allows reading and modification (includes sending/replying)
        "https://www.googleapis.com/auth/gmail.send "   # Explicit to send
        "https://www.googleapis.com/auth/userinfo.email " # To get the user's email
        "https://www.googleapis.com/auth/userinfo.profile" # To get the username
    )

    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": scope,
        "access_type": "offline", # Essential to obtain the refresh_token
        "prompt": "consent", # Ensures the consent screen is always displayed
        "state": str(agent_id) # Pass the agent_id back in the callback for identification
    }
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    return RedirectResponse(auth_url)

# --- OAuth 2.0 Callback Endpoint---
@app.get("/auth/callback")
async def google_auth_callback(request: Request, code: str = None, state: str = None, error: str = None, db: Session = Depends(get_db)):
    """
    Receives the authorization code from Google, exchanges it for tokens, and saves the agent.    """
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authorization error: {error}"
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code not received."
        )

    # Retrieves the agent_id from the 'state' parameter
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'state' parameter (agent_id) in callback."
        )
    try:
        agent_id = int(state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 'state' parameter (not a numeric agent ID)."
        )

    # Busca o agente no banco de dados
    db_agent = db.query(GmailAgent).filter(GmailAgent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found for update."
        )

    # Troca o código de autorização por tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_params = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI, # IMPORTANT: MUST BE THE SAME AS HOME AND GOOGLE CLOUD CONSOLE
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient() as client:
        try:
            # Google expects form parameters (application/x-www-form-urlencoded)
            response = await client.post(token_url, data=token_params)
            response.raise_for_status() # Raises exception for HTTP errors (4xx ou 5xx)
            tokens = response.json()
        except httpx.HTTPStatusError as e:
            # Captures the specific Google error and details it
            print(f"HTTP error when exchanging code for tokens: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error exchanging code for tokens with Google: {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"Network error connecting to Google: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Network error connecting to Google: {e}"
            )

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token") # The access_token is short-lived, no need to save in the DB

    if not refresh_token:
        # This can happen if access_type=offline was not used in /authorize,
        # or if the user did not give consent for offline access.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token not received. Check if 'access_type=offline' was used in /authorize and if the user consented."
        )

    # Optional: Get user information (email and name) to confirm or update
    # It's a good practice to ensure the token is for the expected email address.
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        try:
            userinfo_response = await client.get(userinfo_url, headers=headers)
            userinfo_response.raise_for_status()
            user_info = userinfo_response.json()
            authorized_email = user_info.get("email")
            authorized_name = user_info.get("name")
        except httpx.HTTPStatusError as e:
            print(f"Error getting user information: {e.response.status_code} - {e.response.text}")
            authorized_email = "unknown@gmail.com"
            authorized_name = "Unknown Agent"
        except httpx.RequestError as e:
            print(f"Network error while getting user information: {e}")
            authorized_email = "unknown@gmail.com"
            authorized_name = "Unknown Agent"

    # --- Update the Agent in the Database ---
    # We use the agent_id from the 'state' to find the correct agent.
    cipher = get_cipher_suite()
    encrypted_refresh_token = cipher.encrypt(refresh_token.encode())

    # Updates existing agent with new refresh_token
    db_agent.refresh_token = encrypted_refresh_token
    db_agent.email_gmail = authorized_email # Updates email if user has changed accounts
    db_agent.name = authorized_name # Update the name
    # If you chose to save client_id/secret per agent, they would already be in db_agent
    # and would not need to be updated here unless you want to.

    db.add(db_agent) # Add to persist changes
    db.commit()
    db.refresh(db_agent) # Updates the object with data from the DB

    return {"message": f"Agent {db_agent.name} ({db_agent.email_gmail}) authorized and updated successfully!", "agent_id": db_agent.id}

# --- Your existing POST /agents/ endpoint (for admin or manual testing) ---
@app.post("/agents/")
def create_agent_manual(agent: AgentIn, db: Session = Depends(get_db)):
    # Check if the email already exists to avoid duplicates
    existing_agent = db.query(GmailAgent).filter(GmailAgent.email_gmail == agent.email_gmail).first()
    if existing_agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The agent with this email already exists. Use the authorization flow to update it."
        )

    cipher = get_cipher_suite()
    # The client_id/secret and refresh_token are manually provided here
    encrypted_client_id = cipher.encrypt(agent.client_id.encode())
    encrypted_client_secret = cipher.encrypt(agent.client_secret.encode())
    encrypted_refresh_token = cipher.encrypt(agent.refresh_token.encode())

    db_agent = GmailAgent(
        name=agent.name,
        email_gmail=agent.email_gmail,
        client_id=encrypted_client_id,
        client_secret=encrypted_client_secret,
        refresh_token=encrypted_refresh_token
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return {"id": db_agent.id, "message": "Agente criado com sucesso. Por favor, autorize."}

app.include_router(email_router, prefix="/api", tags=["emails"])
app.include_router(summary_router, prefix="/api", tags=["summary"])
app.include_router(tasks_router, prefix="/api", tags=["tasks"])


