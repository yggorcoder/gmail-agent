import base64
import os
import re # Import to use regular expressions
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from fastapi import HTTPException, status
from email.mime.text import MIMEText

# Scopes required to interact with Gmail (must be consistent with what has been authorized)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

def get_gmail_service(client_id: str, client_secret: str, refresh_token: str):
    """
    Authenticates and returns the Gmail API service to the agent using a refresh_token.
    """
    credentials_info = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'token_uri': 'https://oauth2.googleapis.com/token'
    }

    creds = Credentials.from_authorized_user_info(
        info=credentials_info,
        scopes=SCOPES
    )

    if not creds.valid:
        try:
            creds.refresh(Request())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Não foi possível refrescar o access token. Refresh token inválido ou expirado. Erro: {e}"
            )

    service = build('gmail', 'v1', credentials=creds)
    return service

def send_email(service, to_email: str, from_email: str, subject: str, message_body: str, thread_id: str = None):
    """
    Sends an email using the Gmail API.

    Args:
        service: The authenticated Gmail API service object.
        to_email (str): The recipient's email address.
        from_email (str): The sender's email address (the agent's email).
        subject (str): The subject of the email.
        message_body (str): The body content of the email.
        thread_id (str, optional): The ID of the thread to reply to. Defaults to None.
    """
    try:
        message = MIMEText(message_body)
        message['to'] = to_email
        message['from'] = from_email
        message['subject'] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        body = {'raw': raw_message}
        if thread_id:
            body['threadId'] = thread_id # Add the threadId to ensure it is a reply in the same thread

        send_message = service.users().messages().send(userId='me', body=body).execute()
        print(f"Email enviado para {to_email}! Message Id: {send_message['id']}")
        return send_message
    except Exception as e:
        print(f"Erro ao enviar e-mail para {to_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao enviar e-mail: {e}"
        )


def fetch_recent_emails(client_id: str, client_secret: str, refresh_token: str, max_results: int = 5):
    """
    Fetches the most recent emails from the Gmail inbox, ignoring promotions, spam,
    and other categories, and specific senders.
    Returns a list of dictionaries with sender, subject, body, and labels.
    """
    service = get_gmail_service(client_id, client_secret, refresh_token)
    
    try:
        # Removed labelIds=['INBOX'] to fetch emails from all categories and filter later
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar e-mails: {e}"
        )

    messages = results.get('messages', [])
    emails = []
    
    # Set email categories to ignore
    IGNORED_CATEGORIES = [
        'CATEGORY_PROMOTIONS',
        'CATEGORY_SOCIAL',
        'CATEGORY_UPDATES', # Meta emails often land here
        'CATEGORY_FORUMS',
        'SPAM'
    ]

    # Define specific senders to ignore (case-insensitive)
    # Add the email addresses or domains you want to ignore here
    IGNORED_SENDERS = [
        'security@facebookmail.com',
        'noreply@mail.instagram.com',
        'facebookmail.com', # Domains to grab multiple emails from the same source
        'instagram.com',
        'meta.com',
        'mail.meta.com',
        # Add other senders or domains as needed
    ]

    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            label_ids = msg_data.get('labelIds', [])
            
            should_ignore = False

            # Filter by category (if the email has any of the ignored categories)
            for label in label_ids:
                if label in IGNORED_CATEGORIES:
                    should_ignore = True
                    break

            # Filter by sender (if not already ignored by category)
            if not should_ignore:
                # Extract only the sender's email address (if name is present, e.g. "Name <email@example.com>")
                sender_email_match = re.search(r'<([^>]+)>', sender)
                sender_address = sender_email_match.group(1).lower() if sender_email_match else sender.lower()

                for ignored_sender in IGNORED_SENDERS:
                    # Checks if the ignored sender is contained in the sender's email address
                    if ignored_sender.lower() in sender_address:
                        should_ignore = True
                        break

            if should_ignore:
                print(f"Ignorando e-mail indesejado: '{subject}' de '{sender}' (Labels: {label_ids})")
                # Mark as read to not process again in future runs
                mark_email_as_read(service, msg['id'])
                continue # Skip to the next email
            
            # Extract email body (plain text only)
            body = ''
            if 'parts' in msg_data['payload']:
                for part in msg_data['payload']['parts']:
                    if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            else:
                if 'body' in msg_data['payload'] and 'data' in msg_data['payload']['body']:
                    body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8')
            
            emails.append({
                'id': msg['id'],
                'threadId': msg['threadId'],
                'subject': subject,
                'from': sender,
                'body': body,
                'labelIds': label_ids
            })
        except Exception as e:
            print(f"Erro ao processar mensagem {msg.get('id', 'N/A')}: {e}")
            continue
    return emails


def mark_email_as_read(service, msg_id: str):
    """
    Marks the email with the given ID as read (removes the UNREAD label).
    """
    try:
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao marcar e-mail como lido: {e}"
        )


def fetch_thread_history(service, thread_id: str):
    """
    Fetches the complete history of a Gmail thread.
    Returns a list of messages ordered by date, each with sender, date, and body.
    """
    try:
        thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar histórico do thread: {e}"
        )

    messages = thread.get('messages', [])
    history = []
    for msg in messages:
        headers = msg['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        body = ''
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
        else:
            if 'body' in msg['payload'] and 'data' in msg['payload']['body']:
                body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
        
        history.append({
            'from': sender,
            'date': date,
            'body': body
        })
    return history